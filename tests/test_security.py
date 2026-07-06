"""Тести хешування паролів і JWT (src/auth/security.py)."""

import pytest

from src.auth import security


@pytest.fixture(autouse=True)
def _set_secret(monkeypatch):
    # get_secret_key() читає JWT_SECRET з оточення на кожен виклик.
    monkeypatch.setenv("JWT_SECRET", "test-secret-32chars-minimum-length-ok")


def test_hash_verify_roundtrip():
    stored = security.hash_password("s3cret-pass")
    assert stored.startswith("pbkdf2_sha256$")
    assert security.verify_password("s3cret-pass", stored) is True


def test_verify_rejects_wrong_password():
    stored = security.hash_password("correct")
    assert security.verify_password("wrong", stored) is False


def test_hash_is_salted_unique():
    # Дві хешовки того самого пароля мають різні solt → різні рядки.
    assert security.hash_password("same") != security.hash_password("same")


def test_verify_handles_malformed_hash():
    # Пошкоджений/чужий формат не має кидати виняток — лише False.
    assert security.verify_password("x", "not-a-valid-hash") is False
    assert security.verify_password("x", "") is False


def test_token_roundtrip():
    token = security.create_token(user_id=7, username="alice")
    payload = security.decode_token(token)
    assert payload["sub"] == "alice"
    assert payload["uid"] == 7


def test_expired_token_rejected(monkeypatch):
    from datetime import timedelta

    # Токен, що вже протермінувався.
    monkeypatch.setattr(security, "TOKEN_EXPIRE_HOURS", -1)
    token = security.create_token(user_id=1, username="bob")
    with pytest.raises(security.HTTPException) as exc:
        security.decode_token(token)
    assert exc.value.status_code == 401


def test_token_wrong_secret_rejected(monkeypatch):
    token = security.create_token(user_id=1, username="bob")
    monkeypatch.setenv("JWT_SECRET", "a-completely-different-secret-value-32")
    with pytest.raises(security.HTTPException) as exc:
        security.decode_token(token)
    assert exc.value.status_code == 401


def test_get_secret_key_rejects_forbidden(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "changeme")
    with pytest.raises(RuntimeError):
        security.get_secret_key()


def test_get_secret_key_rejects_too_short(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "short")
    with pytest.raises(RuntimeError):
        security.get_secret_key()
