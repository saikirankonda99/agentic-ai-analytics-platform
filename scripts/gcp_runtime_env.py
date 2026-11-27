"""Load pinned Secret Manager versions into a private Compose env file on a GCE VM.

No credentials are accepted as command arguments. The VM's attached service
account must have access to the three specified secret versions.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirects are not accepted.")


def read_json(url: str, headers: dict[str, str]) -> dict:
    """Disable proxies/redirects so metadata credentials stay on the intended path."""
    with build_opener(ProxyHandler({}), NoRedirect()).open(Request(url, headers=headers), timeout=15) as response:
        raw = response.read(131073)
    if len(raw) > 131072:
        raise ValueError("Response is too large.")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Invalid response.")
    return result


def fetch_secret(project: str, secret: str, version: str, token: str) -> str:
    result = read_json(
        f"https://secretmanager.googleapis.com/v1/projects/{project}/secrets/{secret}/versions/{version}:access",
        {"Authorization": f"Bearer {token}"},
    )
    return base64.b64decode(result["payload"]["data"], validate=True).decode("utf-8")


def checked_users(raw: str) -> str:
    users = json.loads(raw)
    if not isinstance(users, dict) or not users:
        raise ValueError("AUTH_USERS must contain production accounts.")
    personal, shared, roles = set(), set(), set()
    for username, user in users.items():
        if not isinstance(user, dict) or "password" in user:
            raise ValueError("Only password hashes are accepted.")
        team = user.get("team_id", "default-team")
        for identifier in (username, team):
            if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", identifier):
                raise ValueError("Account identifiers must be canonical.")
            if identifier.endswith("-"):
                raise ValueError("Account identifiers must be canonical.")
        if username.rsplit(".", 1)[-1].casefold() == "shared":
            raise ValueError("Reserved account identifier.")
        role = user.get("role", "analyst")
        if role not in {"admin", "analyst", "viewer"}:
            raise ValueError("Invalid account role.")
        roles.add(role)
        value = user.get("password_hash", "")
        if not isinstance(value, str):
            raise ValueError("Invalid password hash.")
        algorithm, rounds, salt, digest = value.split("$", 3)
        if (algorithm != "pbkdf2_sha256" or not 120000 <= int(rounds) <= 1000000
                or len(salt) < 16 or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)):
            raise ValueError("Invalid password hash.")
        workspace = f"{team}.{username}"
        if workspace in personal:
            raise ValueError("Colliding account identifiers.")
        personal.add(workspace)
        shared.add(f"{team}.shared")
    if personal & shared or "admin" not in roles or not roles & {"analyst", "viewer"}:
        raise ValueError("Configure distinct administrator and customer accounts.")
    encoded = json.dumps(users, ensure_ascii=True, separators=(",", ":"))
    # Unicode escapes preserve JSON strings through literal Compose single quotes
    # and python-dotenv, without ambiguous backslash or apostrophe escaping.
    return encoded.replace("\\\\", "\\u005c").replace('\\"', "\\u0022").replace("'", "\\u0027")


def render_env(values: dict[str, str]) -> str:
    if any(not isinstance(v, str) or not v or any(c in v for c in "\r\n\0") for v in values.values()):
        raise ValueError("Secret values must be nonempty, single-line text.")
    key, password = values["OPENAI_API_KEY"], values["POSTGRES_PASSWORD"]
    if not re.fullmatch(r"sk-[A-Za-z0-9_-]{20,}", key):
        raise ValueError("Invalid API credential format.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,}", password):
        raise ValueError("Database password must be URL-safe and at least 24 characters.")
    users = checked_users(values["AUTH_USERS"])
    data = {"OPENAI_API_KEY": key, "AUTH_USERS": users, "POSTGRES_PASSWORD": password}
    return "".join(f"{name}='{value}'\n" for name, value in data.items())


def write_private(path: Path, content: str, replace: bool = False) -> None:
    path = path.absolute()
    if path.name == ".env.example" or not (path.name == ".env" or path.name.startswith(".env.")):
        raise ValueError("Choose a private .env or .env.* destination, never the tracked example.")
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("Symlink destinations are not accepted.")
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    # Crash residue must also match the repository's Git and Docker exclusions.
    temporary = ".env.gcp-runtime-" + secrets.token_hex(16)
    try:
        try:
            existing = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            existing = None
        if existing and (not replace or not stat.S_ISREG(existing.st_mode)):
            raise ValueError("Destination exists; explicit replacement of a regular file is required.")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            # os.replace never follows a destination symlink; it replaces the link.
            if path.is_symlink():
                raise ValueError("Symlink destinations are not accepted.")
            os.replace(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory)
        else:
            os.link(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        os.fsync(directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass
        os.close(directory)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replace", action="store_true")
    for name, default in (("openai", "analytics-openai-key"), ("users", "analytics-auth-users"),
                          ("postgres", "analytics-postgres-password")):
        parser.add_argument(f"--{name}-secret", default=default)
        parser.add_argument(f"--{name}-version", required=True)
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", args.project):
            raise ValueError("Invalid project ID.")
        for name in ("openai", "users", "postgres"):
            if (not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", getattr(args, name + "_secret"))
                    or not re.fullmatch(r"[1-9][0-9]*", getattr(args, name + "_version"))):
                raise ValueError("Use secret IDs and explicit numeric versions.")
        token = read_json(
            "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token",
            {"Metadata-Flavor": "Google"},
        )["access_token"]
        if not isinstance(token, str) or not token or any(c in token for c in "\r\n\0"):
            raise ValueError("Invalid metadata token.")
        values = {
            env: fetch_secret(args.project, getattr(args, name + "_secret"), getattr(args, name + "_version"), token)
            for name, env in (("openai", "OPENAI_API_KEY"), ("users", "AUTH_USERS"), ("postgres", "POSTGRES_PASSWORD"))
        }
        write_private(args.output, render_env(values), args.replace)
    except Exception:
        print("Secret setup failed. Check permissions, pinned versions, account format, and destination; values hidden.",
              file=sys.stderr)
        return 1
    print("Private runtime configuration saved with mode 0600; values hidden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
