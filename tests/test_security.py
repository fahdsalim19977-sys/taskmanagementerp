import hashlib

from utils.security import hash_password, is_legacy_password_hash, verify_password


def test_modern_password_hash_verifies():
    password = "Strong-Test-Password-2026!"
    stored = hash_password(password)

    assert stored != password
    assert verify_password(stored, password)
    assert not verify_password(stored, "wrong-password")


def test_legacy_sha256_password_can_be_migrated():
    password = "legacy-password"
    stored = hashlib.sha256(password.encode("utf-8")).hexdigest()

    assert is_legacy_password_hash(stored)
    assert verify_password(stored, password)
    assert not verify_password(stored, "wrong-password")


def test_invalid_password_hash_is_rejected():
    assert not verify_password("", "password")
    assert not verify_password("not-a-valid-hash", "password")
