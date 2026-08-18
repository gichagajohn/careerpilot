"""Fernet encryption for personally identifiable information (PII).

Fields like phone numbers and TSC numbers are encrypted at rest. The key
comes from the ENCRYPTION_KEY environment variable (generate with
`python scripts/gen_key.py`).
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


def _fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Generate one with `python scripts/gen_key.py` "
            "and add it to your .env file."
        )
    return Fernet(key.encode())


def encrypt_text(plain: str | None) -> str | None:
    """Encrypt a value for storage. None -> None."""
    if plain is None or plain.strip() == "":
        return None
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_text(token: str | None) -> str | None:
    """Decrypt a value read from storage. Invalid/empty -> None."""
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
