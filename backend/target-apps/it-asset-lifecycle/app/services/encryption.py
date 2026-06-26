"""Fernet encryption service for license keys."""
from __future__ import annotations

from cryptography.fernet import Fernet

from app.config import get_settings


def _get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.asset_encryption_key
    if not key:
        raise RuntimeError("ASSET_ENCRYPTION_KEY is not configured")
    return Fernet(key.encode("utf-8") if isinstance(key, str) else key)


def encrypt_license_key(plaintext: str) -> str:
    """Encrypt a license key; returns base64-encoded ciphertext."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_license_key(ciphertext: str) -> str:
    """Decrypt a license key ciphertext to plaintext."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
