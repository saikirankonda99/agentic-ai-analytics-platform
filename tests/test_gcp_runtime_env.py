import base64
import fnmatch
import io
import json
from pathlib import Path
import stat
import subprocess

from dotenv import dotenv_values
import pytest

from backend.auth_sessions import _configured_user_snapshot, hash_password
from scripts import gcp_runtime_env as loader


@pytest.fixture
def values():
    users = {
        "owner": {"role": "admin", "team_id": "pilot", "password_hash": hash_password("owner-test-password"),
                  "display_name": "Owner's $budget ${UNSET} \\ path \"quoted\""},
        "analyst": {"role": "analyst", "team_id": "pilot", "password_hash": hash_password("analyst-test-password")},
    }
    return {"OPENAI_API_KEY": "sk-" + "f" * 32, "AUTH_USERS": json.dumps(users), "POSTGRES_PASSWORD": "p" * 32}


def arguments(path):
    return ["--project", "test-project", "--output", str(path), "--openai-version", "1",
            "--users-version", "2", "--postgres-version", "3"]


def fake_cloud(monkeypatch, values):
    calls = []

    def read(url, headers):
        calls.append((url, headers))
        if url.startswith("http://169.254.169.254/"):
            return {"access_token": "private-metadata-token"}
        for name, env in (("analytics-openai-key", "OPENAI_API_KEY"), ("analytics-auth-users", "AUTH_USERS"),
                          ("analytics-postgres-password", "POSTGRES_PASSWORD")):
            if f"/secrets/{name}/" in url:
                return {"payload": {"data": base64.b64encode(values[env].encode()).decode()}}
        raise AssertionError("Unexpected test endpoint.")

    monkeypatch.setattr(loader, "read_json", read)
    return calls


def test_secret_transport_and_env_roundtrip_are_private(tmp_path, monkeypatch, capsys, values):
    calls = fake_cloud(monkeypatch, values)
    output = tmp_path / ".env"
    assert loader.main(arguments(output)) == 0
    actual = dotenv_values(stream=io.StringIO(output.read_text()), interpolate=False)
    assert actual["OPENAI_API_KEY"] == values["OPENAI_API_KEY"]
    assert actual["POSTGRES_PASSWORD"] == values["POSTGRES_PASSWORD"]
    assert json.loads(actual["AUTH_USERS"]) == json.loads(values["AUTH_USERS"])
    assert len(_configured_user_snapshot(actual["AUTH_USERS"], True, ())) == 2
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert all("/versions/" in url for url, _ in calls[1:])
    assert [url.rsplit("/", 1)[-1] for url, _ in calls[1:]] == ["1:access", "2:access", "3:access"]
    logged = capsys.readouterr()
    assert not logged.err
    assert "private-metadata-token" not in logged.out
    assert all(value not in logged.out for value in values.values())
    # Compose's single-quoted literal grammar must preserve hash dollar signs.
    assert "AUTH_USERS='" in output.read_text()
    assert "pbkdf2_sha256$120000$" in output.read_text()


@pytest.mark.parametrize("bad", ["latest", "0", "1/../../other", "1\n"])
def test_versions_are_pinned_before_metadata_access(tmp_path, monkeypatch, bad):
    monkeypatch.setattr(loader, "read_json", lambda *a: pytest.fail("must not contact metadata"))
    args = arguments(tmp_path / ".env")
    args[args.index("--openai-version") + 1] = bad
    assert loader.main(args) == 1
    assert not (tmp_path / ".env").exists()


@pytest.mark.parametrize("field,bad", [
    ("OPENAI_API_KEY", "sk-value\nINJECTED=1"),
    ("POSTGRES_PASSWORD", "short"),
    ("POSTGRES_PASSWORD", "p" * 32 + "@"),
    ("AUTH_USERS", "{bad-json"),
    ("AUTH_USERS", "[]"),
])
def test_invalid_secret_does_not_replace_private_file(tmp_path, monkeypatch, capsys, values, field, bad):
    output = tmp_path / ".env"
    output.write_text("previous-private-configuration")
    values[field] = bad
    fake_cloud(monkeypatch, values)
    assert loader.main(arguments(output) + ["--replace"]) == 1
    assert output.read_text() == "previous-private-configuration"
    logged = capsys.readouterr()
    assert logged.out == ""
    assert "Secret setup failed." in logged.err
    assert bad not in logged.err
    assert not list(tmp_path.glob(".env.gcp-runtime-*"))


def test_http_error_payload_is_not_printed(tmp_path, monkeypatch, capsys):
    def fail(*args):
        raise RuntimeError("private-token private-key provider-response")
    monkeypatch.setattr(loader, "read_json", fail)
    assert loader.main(arguments(tmp_path / ".env")) == 1
    logged = capsys.readouterr()
    assert "private-token" not in logged.err
    assert "private-key" not in logged.err
    assert "provider-response" not in logged.err


def test_existing_file_requires_explicit_replace(tmp_path):
    target = tmp_path / ".env"
    target.write_text("keep")
    with pytest.raises(ValueError):
        loader.write_private(target, "replacement")
    assert target.read_text() == "keep"
    loader.write_private(target, "replacement", replace=True)
    assert target.read_text() == "replacement"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_symlink_destinations_and_parents_are_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    victim = outside / ".env"
    victim.write_text("keep")
    link = tmp_path / ".env.link"
    link.symlink_to(victim)
    with pytest.raises(ValueError):
        loader.write_private(link, "replacement", replace=True)
    directory_link = tmp_path / "directory-link"
    directory_link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        loader.write_private(directory_link / ".env", "replacement", replace=True)
    assert victim.read_text() == "keep"


def test_concurrent_destination_creation_is_not_overwritten(tmp_path, monkeypatch):
    target = tmp_path / ".env"
    original_link = loader.os.link

    def race(source, destination, **kwargs):
        target.write_text("concurrent-config")
        return original_link(source, destination, **kwargs)

    monkeypatch.setattr(loader.os, "link", race)
    with pytest.raises(FileExistsError):
        loader.write_private(target, "new-secret")
    assert target.read_text() == "concurrent-config"
    assert not list(tmp_path.glob(".env.gcp-runtime-*"))


@pytest.mark.parametrize("name", ["README.md", ".env.example", "public.env"])
def test_only_ignored_env_destinations_are_allowed(tmp_path, name):
    target = tmp_path / name
    target.write_text("keep")
    with pytest.raises(ValueError):
        loader.write_private(target, "secret", replace=True)
    assert target.read_text() == "keep"


def test_temporary_secret_file_is_excluded_from_git_and_docker(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    original_link = loader.os.link

    def inspect_temporary(source, destination, **kwargs):
        assert subprocess.run(["git", "check-ignore", "--quiet", source], cwd=root).returncode == 0
        excluded = False
        for rule in (root / ".dockerignore").read_text().splitlines():
            rule = rule.strip()
            if rule and not rule.startswith("#") and fnmatch.fnmatchcase(source, rule.lstrip("!")):
                excluded = not rule.startswith("!")
        assert excluded, "Temporary credential file must be excluded from Docker build context."
        return original_link(source, destination, **kwargs)

    monkeypatch.setattr(loader.os, "link", inspect_temporary)
    loader.write_private(tmp_path / ".env", "synthetic-secret")


@pytest.mark.parametrize("change", ["plaintext", "weak_hash", "shared", "missing_customer", "collision"])
def test_production_account_constraints(values, change):
    users = json.loads(values["AUTH_USERS"])
    if change == "plaintext":
        users["owner"]["password"] = "unwanted-plaintext"
    elif change == "weak_hash":
        users["owner"]["password_hash"] = "pbkdf2_sha256$1$short$" + "0" * 64
    elif change == "shared":
        users["shared"] = users.pop("owner")
    elif change == "missing_customer":
        users.pop("analyst")
    else:
        users["a.owner"] = dict(users["owner"], team_id="pilot")
        users["owner"]["team_id"] = "pilot.a"
    values["AUTH_USERS"] = json.dumps(users)
    with pytest.raises((ValueError, TypeError)):
        loader.render_env(values)
