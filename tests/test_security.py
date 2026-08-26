import hashlib

from models import hash_password, verify_password, is_legacy_password_hash


def test_new_password_hash_verifies():
    password = "Strong-Test-Password-2026!"
    stored = hash_password(password)

    assert stored != password
    assert verify_password(stored, password)
    assert not verify_password(stored, "wrong-password")


def test_legacy_sha256_hash_verifies_for_migration():
    password = "legacy-password"
    stored = hashlib.sha256(password.encode()).hexdigest()

    assert is_legacy_password_hash(stored)
    assert verify_password(stored, password)
    assert not verify_password(stored, "wrong-password")


def test_empty_or_invalid_hash_is_rejected():
    assert not verify_password("", "password")
    assert not verify_password("not-a-valid-password-hash", "password")
