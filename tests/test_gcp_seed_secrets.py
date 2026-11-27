import getpass
import json
import subprocess
import warnings

import pytest

from backend.auth_sessions import _configured_user_snapshot, verify_password
from scripts import gcp_seed_secrets as seed


API_KEY = "sk-" + "f" * 32
ADMIN_PASSWORD = "admin-private-passphrase"
ANALYST_PASSWORD = "analyst-private-passphrase"


@pytest.fixture
def cloud(monkeypatch):
    calls = []
    versions = {}

    def run(args, **kwargs):
        calls.append((args, kwargs))
        secret = args[4]
        if args[3] == "list":
            output = json.dumps(versions.get(secret, []))
        else:
            assert args[3] == "add"
            versions[secret] = [{"state": "ENABLED"}]
            output = f"projects/123456789/secrets/{secret}/versions/1\n"
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(seed.subprocess, "run", run)
    monkeypatch.setattr(seed, "terminal_available", lambda: True)
    return calls, versions


def inputs(monkeypatch, values=None):
    answers = iter(values if values is not None else
                   [API_KEY, ADMIN_PASSWORD, ADMIN_PASSWORD, ANALYST_PASSWORD, ANALYST_PASSWORD])
    monkeypatch.setattr(seed.getpass, "getpass", lambda *a, **k: next(answers))


def test_private_inputs_use_stdin_and_compatible_hashes(monkeypatch, capsys, cloud):
    inputs(monkeypatch)
    assert seed.main(["--project", "test-project"]) == 0
    calls, _ = cloud
    writes = [(args, kwargs) for args, kwargs in calls if args[3] == "add"]
    assert len(writes) == 3
    assert len(calls) == 9  # All resources checked both before and after private input.
    payloads = {args[4]: kwargs["input"] for args, kwargs in writes}
    users = json.loads(payloads["analytics-auth-users"])
    assert verify_password(ADMIN_PASSWORD, users["admin"]["password_hash"])
    assert verify_password(ANALYST_PASSWORD, users["analyst"]["password_hash"])
    assert len(_configured_user_snapshot(payloads["analytics-auth-users"], True, ())) == 2
    assert payloads["analytics-openai-key"] == API_KEY
    assert len(payloads["analytics-postgres-password"]) >= 32
    output = capsys.readouterr()
    for args, kwargs in calls:
        assert "--project=test-project" in args
        assert "--no-log-http" in args and "--verbosity=none" in args
        assert kwargs["env"]["CLOUDSDK_CORE_DISABLE_FILE_LOGGING"] == "true"
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is True
        assert kwargs.get("shell", False) is False
        for value in (API_KEY, ADMIN_PASSWORD, ANALYST_PASSWORD, *payloads.values()):
            assert value not in " ".join(args)
            assert value not in output.out + output.err
    assert "analytics-openai-key: 1" in output.out
    assert not output.err


@pytest.mark.parametrize("state", ["ENABLED", "DISABLED", "DESTROYED"])
def test_any_existing_version_blocks_inputs_and_writes(monkeypatch, capsys, cloud, state):
    calls, versions = cloud
    versions["analytics-postgres-password"] = [{"state": state}]
    monkeypatch.setattr(seed.getpass, "getpass", lambda *a, **k: pytest.fail("must refuse before asking for secrets"))
    assert seed.main(["--project", "test-project"]) == 1
    assert all(args[3] == "list" for args, _ in calls)
    assert "Existing secret versions found" in capsys.readouterr().err


def test_version_created_during_input_blocks_all_writes(monkeypatch, cloud):
    calls, versions = cloud
    answers = iter([API_KEY, ADMIN_PASSWORD, ADMIN_PASSWORD, ANALYST_PASSWORD, ANALYST_PASSWORD])

    def read(*args, **kwargs):
        versions["analytics-auth-users"] = [{"state": "ENABLED"}]
        return next(answers)

    monkeypatch.setattr(seed.getpass, "getpass", read)
    assert seed.main(["--project", "test-project"]) == 1
    assert all(args[3] == "list" for args, _ in calls)


@pytest.mark.parametrize("answers", [
    [API_KEY, ADMIN_PASSWORD, "mismatched-secret"],
    [API_KEY, "short", "short"],
    [API_KEY, ADMIN_PASSWORD, ADMIN_PASSWORD, ADMIN_PASSWORD, ADMIN_PASSWORD],
    ["malformed-private-key", ADMIN_PASSWORD, ADMIN_PASSWORD, ANALYST_PASSWORD, ANALYST_PASSWORD],
])
def test_invalid_private_values_never_create_a_version(monkeypatch, capsys, cloud, answers):
    inputs(monkeypatch, answers)
    assert seed.main(["--project", "test-project"]) == 1
    calls, _ = cloud
    assert all(args[3] == "list" for args, _ in calls)
    output = capsys.readouterr()
    assert all(value not in output.out + output.err for value in answers)


def test_partial_failure_reports_only_confirmed_metadata_and_redacts_provider_error(monkeypatch, capsys, cloud):
    inputs(monkeypatch)
    original = seed.subprocess.run

    def fail_second(args, **kwargs):
        if args[3] == "add" and args[4] == "analytics-auth-users":
            raise subprocess.CalledProcessError(1, args, output=API_KEY, stderr=kwargs["input"])
        return original(args, **kwargs)

    monkeypatch.setattr(seed.subprocess, "run", fail_second)
    assert seed.main(["--project", "test-project"]) == 1
    output = capsys.readouterr()
    assert "Confirmed created: analytics-openai-key, version 1" in output.err
    assert "outcome uncertain for analytics-auth-users" in output.err
    assert "Do not retry or rotate automatically" in output.err
    assert "pbkdf2_sha256" not in output.err
    assert API_KEY not in output.out + output.err
    assert "analytics-postgres-password" not in cloud[1]


def test_no_tty_refuses_before_contacting_cloud(monkeypatch, cloud, capsys):
    monkeypatch.setattr(seed, "terminal_available", lambda: False)
    assert seed.main(["--project", "test-project"]) == 1
    assert cloud[0] == []
    assert "interactive private terminal" in capsys.readouterr().err


def test_getpass_echo_fallback_is_blocked(monkeypatch, cloud, capsys):
    def echo_warning(*args, **kwargs):
        warnings.warn("echo disabled unavailable", getpass.GetPassWarning)
        pytest.fail("must stop before fallback could read an echoed input")

    monkeypatch.setattr(seed.getpass, "getpass", echo_warning)
    assert seed.main(["--project", "test-project"]) == 1
    assert all(args[3] == "list" for args, _ in cloud[0])
    assert "echo disabled unavailable" not in capsys.readouterr().err


@pytest.mark.parametrize("project", ["--other-project", "bad/project", "test-project\n"])
def test_invalid_project_never_invokes_gcloud(project, cloud):
    assert seed.main([f"--project={project}"]) == 1
    assert cloud[0] == []


def test_preflight_failure_does_not_read_input_or_echo_error(monkeypatch, capsys, cloud):
    def fail(*args, **kwargs):
        raise RuntimeError("private-provider-response " + API_KEY)

    monkeypatch.setattr(seed.subprocess, "run", fail)
    monkeypatch.setattr(seed.getpass, "getpass", lambda *a, **k: pytest.fail("no inputs after preflight failure"))
    assert seed.main(["--project", "test-project"]) == 1
    assert API_KEY not in capsys.readouterr().err


def test_accidentally_supplied_credential_argument_is_not_echoed(cloud, capsys):
    assert seed.main(["--project", "test-project", "--api-key", API_KEY]) == 1
    assert cloud[0] == []
    output = capsys.readouterr()
    assert API_KEY not in output.out + output.err
