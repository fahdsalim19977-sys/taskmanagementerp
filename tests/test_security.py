import hashlib

from routes.auth import _is_legacy_sha256, _verify_password
from models import hash_password


def test_new_password_hash_verifies():
    password = 'Strong-Test-Password-123!'
    stored = hash_password(password)

    assert stored.startswith('$2')
    assert _verify_password(password, stored) is True
    assert _verify_password('wrong-password', stored) is False


def test_legacy_sha256_hash_is_detected_and_verified():
    password = 'LegacyPassword123!'
    stored = hashlib.sha256(password.encode('utf-8')).hexdigest()

    assert _is_legacy_sha256(stored) is True
    assert _verify_password(password, stored) is True
    assert _verify_password('wrong-password', stored) is False


def test_invalid_hash_is_rejected():
    assert _verify_password('password', 'not-a-valid-hash') is False
