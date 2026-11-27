"""Exercise a disposable CI stack without live AI or production credentials."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PASSWORD = "disposable-ci-smoke-password"


def prepare() -> None:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", PASSWORD.encode(), salt.encode(), 120_000).hex()
    users = {"stack-admin": {"password_hash": f"pbkdf2_sha256$120000${salt}${digest}",
                              "display_name": "Stack Check", "team_id": "stack-test", "role": "admin"}}
    # Exclusive creation prevents this CI helper from replacing a developer's key file.
    fd = os.open(".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(f"AUTH_USERS='{json.dumps(users)}'\n")
        handle.write(f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\nOPENAI_API_KEY=\n")
    print("Disposable stack configuration prepared; no live API key configured.")


def request(path: str, *, method: str = "GET", body=None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Session-Token"] = token
    req = Request("http://127.0.0.1:8000" + path, data=json.dumps(body).encode() if body is not None else None,
                  headers=headers, method=method)
    with urlopen(req, timeout=15) as response:
        return json.loads(response.read())


def verify() -> None:
    assert Path(".env").is_file(), "Prepare the isolated CI stack first."
    with urlopen("http://127.0.0.1:8501/_stcore/health", timeout=15) as response:
        assert response.status == 200
    assert request("/health")["status"] == "ok"
    session = request("/auth/login", method="POST", body={"username": "stack-admin", "password": PASSWORD})["session"]
    token = session["session_token"]
    assert request("/auth/session", token=token)["authenticated"]
    job = request("/execute", method="POST", token=token, body={"question": "How many customers are there?"})
    assert job["execution_mode"] == "analytics"
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = request(f"/workflow/{job['workflow_id']}/result", token=token)
        if result["status"] in {"completed", "failed"}:
            break
        time.sleep(0.5)
    else:
        raise AssertionError("The external worker did not finish the queued request.")
    assert result["status"] == "failed", "Missing credentials must not produce a fabricated analytics result."
    assert result["result"] is None or result["result"].get("error"), "A failed request must not claim success."
    assert request("/auth/logout", method="POST", body={"session_token": token})["revoked"]
    try:
        request("/auth/session", token=token)
    except HTTPError as error:
        assert error.code == 401
    else:
        raise AssertionError("Revoked session remained valid.")
    print("Frontend, API, PostgreSQL authentication, durable worker, and logout checks passed.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "verify"}:
        raise SystemExit("Usage: python ops/stack_smoke.py prepare|verify")
    {"prepare": prepare, "verify": verify}[sys.argv[1]]()
