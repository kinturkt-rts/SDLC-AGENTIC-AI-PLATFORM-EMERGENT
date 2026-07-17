"""Verify seed password hashing works correctly.

Seed users in 008_seed.sql use password: BenefitsDemo1!
"""
from app.security import hash_password, verify_password

_SEED_PASSWORD = "BenefitsDemo1!"


def test_hash_and_verify_seed_password():
    """Ensure the seed password can be hashed and verified."""
    hashed = hash_password(_SEED_PASSWORD)
    assert hashed.startswith("$2")
    assert verify_password(_SEED_PASSWORD, hashed)


def test_wrong_password_rejected():
    hashed = hash_password(_SEED_PASSWORD)
    assert not verify_password("WrongPassword!", hashed)
