import time
import pytest
from app import auth, config


def test_generated_secret_is_persisted(tmp_path, monkeypatch):
    monkeypatch.delenv("CHURCH_SESSION_SECRET", raising=False)
    monkeypatch.setattr(auth, "WORKSPACE_DIR", tmp_path)
    first = auth.signing_key()
    assert (tmp_path / ".session_secret").exists()
    assert len((tmp_path / ".session_secret").read_text()) == 64
    assert auth.signing_key() == first


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "127.0.0.2", "::1"])
def test_loopback_can_run_without_password(host, monkeypatch):
    monkeypatch.delenv("CHURCH_PASSWORD", raising=False)
    config.validate_bind_host(host)


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.1"])
def test_external_bind_requires_password(host, monkeypatch):
    monkeypatch.delenv("CHURCH_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="CHURCH_PASSWORD"):
        config.validate_bind_host(host)
    monkeypatch.setenv("CHURCH_PASSWORD", "test-password")
    config.validate_bind_host(host)


def test_expired_login_attempts_are_pruned():
    auth._attempts["expired"] = [time.time() - 120]
    auth._attempts["recent"] = [time.time()]
    auth.prune_attempts()
    assert "expired" not in auth._attempts
    assert "recent" in auth._attempts
    auth._attempts.clear()
