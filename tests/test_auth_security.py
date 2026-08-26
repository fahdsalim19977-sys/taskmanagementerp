import hashlib

from models import hash_password, verify_password


def test_bcrypt_hash_verifies():
    password = "Strong-Test-Password!123"
    hashed = hash_password(password)

    assert hashed.startswith("$2")
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_legacy_sha256_hash_migrates():
    password = "legacy-password"
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

    assert verify_password(password, legacy_hash) is True
    assert verify_password("wrong-password", legacy_hash) is False


def test_invalid_hash_fails_closed():
    assert verify_password("anything", "not-a-valid-hash") is False
