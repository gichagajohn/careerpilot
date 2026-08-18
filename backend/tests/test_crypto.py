"""PII encryption round-trip tests."""
from __future__ import annotations

from app.core.crypto import decrypt_text, encrypt_text


def test_roundtrip():
    plain = "0114094974"
    token = encrypt_text(plain)
    assert token != plain
    assert decrypt_text(token) == plain


def test_none_handling():
    assert encrypt_text(None) is None
    assert encrypt_text("") is None
    assert decrypt_text(None) is None


def test_garbage_token_returns_none():
    assert decrypt_text("not-a-valid-fernet-token") is None
