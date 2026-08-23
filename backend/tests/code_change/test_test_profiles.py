import json

import pytest

from deerflow.code_change.test_profiles import TEST_PROFILES_ENV_VAR, load_test_profiles


def test_test_profiles_default_to_server_owned_commands(monkeypatch):
    monkeypatch.delenv(TEST_PROFILES_ENV_VAR, raising=False)

    profiles = load_test_profiles()

    assert profiles == {
        "python-pytest": "python3 -m pytest -q",
        "go-test": "go test ./...",
        "frontend-check": "pnpm check",
    }


def test_test_profiles_accept_only_json_argument_arrays(monkeypatch):
    monkeypatch.setenv(TEST_PROFILES_ENV_VAR, json.dumps({"safe": ["python3", "-m", "pytest", "-q"]}))

    assert load_test_profiles()["safe"] == "python3 -m pytest -q"

    monkeypatch.setenv(TEST_PROFILES_ENV_VAR, json.dumps({"unsafe": "python3 -c 'arbitrary'"}))
    with pytest.raises(ValueError, match="string array"):
        load_test_profiles()
