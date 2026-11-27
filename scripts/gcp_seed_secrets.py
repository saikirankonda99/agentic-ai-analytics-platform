"""Initialize three empty pilot secrets using private terminal input and gcloud.

Run once, with one operator, in an authenticated Google Cloud Shell. This is
not a password-rotation tool. It never reads existing secret payloads.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import warnings

if __package__:
    from .gcp_runtime_env import render_env
else:
    from gcp_runtime_env import render_env


SECRET_ENVS = {
    "analytics-openai-key": "OPENAI_API_KEY",
    "analytics-auth-users": "AUTH_USERS",
    "analytics-postgres-password": "POSTGRES_PASSWORD",
}


class ExistingVersions(Exception):
    """An initialization target already contains at least one version."""


class InputRejected(Exception):
    """A private input failed validation without exposing its value."""


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes unexpected arguments, which could be a pasted key.
        raise InputRejected("Use --project PROJECT_ID only; enter credentials at the hidden prompts.")


def terminal_available() -> bool:
    return sys.stdin.isatty() and sys.stderr.isatty()


def run_gcloud(project: str, arguments: list[str], value: str | None = None) -> str:
    environment = dict(os.environ)
    environment.update({
        "CLOUDSDK_CORE_DISABLE_FILE_LOGGING": "true",
        "CLOUDSDK_CORE_LOG_HTTP": "false",
        "CLOUDSDK_CORE_DISABLE_PROMPTS": "true",
    })
    result = subprocess.run(
        ["gcloud", *arguments, f"--project={project}", "--quiet", "--no-log-http", "--verbosity=none"],
        input=value, capture_output=True, text=True, encoding="utf-8", check=True, timeout=60, env=environment,
    )
    return result.stdout.strip()


def require_empty(project: str) -> None:
    for secret in SECRET_ENVS:
        # No state filter: disabled and destroyed versions also block a rerun.
        versions = json.loads(run_gcloud(project, [
            "secrets", "versions", "list", secret, "--limit=1", "--format=json",
        ]))
        if not isinstance(versions, list):
            raise ValueError("Invalid metadata response.")
        if versions:
            raise ExistingVersions(secret)


def private_input(prompt: str) -> str:
    # getpass otherwise falls back to echoed stdin on an unsuitable terminal.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(prompt, stream=sys.stderr)


def password_for(username: str) -> str:
    password = private_input(f"New password for {username} (at least 16 characters): ")
    confirmation = private_input(f"Confirm password for {username}: ")
    if not secrets.compare_digest(password.encode("utf-8"), confirmation.encode("utf-8")):
        raise InputRejected("Password confirmation did not match; nothing was written.")
    if not 16 <= len(password) <= 1024 or any(character in password for character in "\r\n\0"):
        raise InputRejected("Use a single-line password of 16 to 1024 characters; nothing was written.")
    return password


def password_hash(password: str) -> str:
    # Exact format used by backend.auth_sessions.hash_password; stdlib only.
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def collect_values() -> dict[str, str]:
    api_key = private_input("Existing OpenAI project API key (hidden): ")
    admin_password = password_for("admin")
    analyst_password = password_for("analyst")
    if secrets.compare_digest(admin_password.encode("utf-8"), analyst_password.encode("utf-8")):
        raise InputRejected("Use different admin and analyst passwords; nothing was written.")
    users = {
        "admin": {"role": "admin", "team_id": "pilot", "display_name": "Pilot administrator",
                  "password_hash": password_hash(admin_password)},
        "analyst": {"role": "analyst", "team_id": "pilot", "display_name": "Pilot analyst",
                    "password_hash": password_hash(analyst_password)},
    }
    values = {"OPENAI_API_KEY": api_key, "AUTH_USERS": json.dumps(users),
              "POSTGRES_PASSWORD": secrets.token_urlsafe(32)}
    render_env(values)  # Validate exactly as the VM loader does, without writing a file.
    return values


def main(argv: list[str] | None = None) -> int:
    parser = PrivateArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--project", required=True)
    try:
        args = parser.parse_args(argv)
    except InputRejected as error:
        print(str(error), file=sys.stderr)
        return 1
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", args.project):
        print("Invalid project ID; nothing was written.", file=sys.stderr)
        return 1
    if not terminal_available():
        print("An interactive private terminal is required; nothing was written.", file=sys.stderr)
        return 1
    print(f"Target project: {args.project}")
    print("Initialize only these empty secrets: " + ", ".join(SECRET_ENVS))
    print("Use your EXISTING OpenAI key. Login names will be admin and analyst, in team pilot.")
    print("Input is hidden. Keep both login passwords in your password manager. Run only one setup at a time.")
    completed: dict[str, str] = {}
    writing: str | None = None
    try:
        require_empty(args.project)
        values = collect_values()
        require_empty(args.project)  # Recheck after the user has finished typing.
        for secret, env_name in SECRET_ENVS.items():
            writing = secret
            name = run_gcloud(args.project, [
                "secrets", "versions", "add", secret, "--data-file=-", "--format=value(name)",
            ], values[env_name])
            match = re.fullmatch(
                rf"projects/(?:[0-9]+|{re.escape(args.project)})/secrets/{secret}/versions/([1-9][0-9]*)", name,
            )
            if not match:
                raise ValueError("Invalid version metadata.")
            completed[secret] = match.group(1)
            writing = None
    except ExistingVersions:
        print("Existing secret versions found. Initialization refused; nothing was written.", file=sys.stderr)
        return 1
    except InputRejected as error:
        print(str(error), file=sys.stderr)
        return 1
    except (Exception, KeyboardInterrupt):
        print("Secret setup stopped; credential values and provider errors are hidden.", file=sys.stderr)
        if writing:
            print(f"Write outcome uncertain for {writing}; inspect version metadata before taking action.", file=sys.stderr)
        for secret, version in completed.items():
            print(f"Confirmed created: {secret}, version {version}", file=sys.stderr)
        print("Do not retry or rotate automatically. Inspect version metadata and resolve the interruption.", file=sys.stderr)
        return 1
    print("Created secret versions (record these numbers for the VM loader):")
    for secret, version in completed.items():
        print(f"{secret}: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
