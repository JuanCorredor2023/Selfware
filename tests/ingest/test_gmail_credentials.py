"""ingest/gmail.py, `get_credentials`: local OAuth vs. the non-interactive login
a GitHub Actions run needs. The Google auth classes are replaced, and the
secrets folder points at tmp_path, so nothing real is read or written."""

import json

import pytest
from google.auth.exceptions import RefreshError

from selfware.ingest import gmail


class FakeCreds:
    def __init__(self, valid=True, expired=False, refresh_token="refresh", fail=None):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.refreshed = False
        self._fail = fail

    def refresh(self, request):
        if self._fail:
            raise self._fail
        self.refreshed = True
        self.valid = True
        self.expired = False

    def to_json(self):
        return json.dumps({"token": "fake", "refreshed": self.refreshed})


class ForbiddenFlow:
    """Stands in for InstalledAppFlow when the browser login must not run."""

    @staticmethod
    def from_client_secrets_file(*args, **kwargs):
        raise AssertionError("the browser login flow must not run here")


@pytest.fixture
def secrets_dir(tmp_path, monkeypatch):
    directory = tmp_path / "secrets"
    monkeypatch.setattr(gmail, "SECRETS_DIR", directory)
    monkeypatch.setattr(gmail, "TOKEN_FILE", directory / "token.json")
    monkeypatch.setattr(gmail, "CREDENTIALS_FILE", directory / "credentials.json")
    monkeypatch.delenv("GMAIL_TOKEN_JSON", raising=False)
    return directory


def stored_creds(monkeypatch, secrets_dir, creds):
    secrets_dir.mkdir(parents=True, exist_ok=True)
    (secrets_dir / "token.json").write_text("{}")
    monkeypatch.setattr(
        gmail.Credentials, "from_authorized_user_file", lambda *a, **k: creds
    )


def test_valid_token_is_used_without_refresh(monkeypatch, secrets_dir):
    creds = FakeCreds(valid=True)
    stored_creds(monkeypatch, secrets_dir, creds)
    monkeypatch.setattr(gmail, "InstalledAppFlow", ForbiddenFlow)

    assert gmail.get_credentials() is creds
    assert not creds.refreshed


def test_expired_token_is_refreshed_and_saved(monkeypatch, secrets_dir):
    creds = FakeCreds(valid=False, expired=True)
    stored_creds(monkeypatch, secrets_dir, creds)
    monkeypatch.setattr(gmail, "InstalledAppFlow", ForbiddenFlow)

    assert gmail.get_credentials() is creds
    assert creds.refreshed
    assert json.loads((secrets_dir / "token.json").read_text())["refreshed"] is True


def test_missing_token_runs_local_flow_and_creates_dir(monkeypatch, secrets_dir):
    creds = FakeCreds()

    class LocalFlow:
        @staticmethod
        def from_client_secrets_file(path, scopes):
            assert scopes == gmail.SCOPES
            return LocalFlow()

        def run_local_server(self, **kwargs):
            return creds

    monkeypatch.setattr(gmail, "InstalledAppFlow", LocalFlow)

    assert gmail.get_credentials() is creds
    assert (secrets_dir / "token.json").exists()


@pytest.mark.xfail(
    strict=True,
    reason="no non-interactive login yet: CI would hang on the browser flow",
)
def test_ci_token_from_env_never_opens_browser(monkeypatch, secrets_dir):
    creds = FakeCreds(valid=True)
    monkeypatch.setenv("GMAIL_TOKEN_JSON", json.dumps({"refresh_token": "r"}))
    monkeypatch.setattr(
        gmail.Credentials, "from_authorized_user_info", lambda *a, **k: creds
    )
    monkeypatch.setattr(gmail, "InstalledAppFlow", ForbiddenFlow)

    assert gmail.get_credentials() is creds


@pytest.mark.xfail(
    strict=True,
    reason="no non-interactive login yet: CI would hang on the browser flow",
)
def test_ci_refresh_error_fails(monkeypatch, secrets_dir):
    creds = FakeCreds(valid=False, expired=True, fail=RefreshError("revoked"))
    monkeypatch.setenv("GMAIL_TOKEN_JSON", json.dumps({"refresh_token": "r"}))
    monkeypatch.setattr(
        gmail.Credentials, "from_authorized_user_info", lambda *a, **k: creds
    )
    monkeypatch.setattr(gmail, "InstalledAppFlow", ForbiddenFlow)

    with pytest.raises(RefreshError):
        gmail.get_credentials()
