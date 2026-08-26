"""Security helpers for authentication and password migration."""

import hashlib

from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password: str) -> str:
    """Create a password-specific, salted hash."""
    return generate_password_hash(password)


def is_legacy_password_hash(stored_password: str) -> bool:
    """Return True for the old unsalted SHA-256 format used by the app."""
    return bool(stored_password) and len(stored_password) == 64 and all(
        char in "0123456789abcdef" for char in stored_password.lower()
    )


def verify_password(stored_password: str, supplied_password: str) -> bool:
    """Verify modern hashes and safely support legacy SHA-256 during migration."""
    if not stored_password or supplied_password is None:
        return False

    if is_legacy_password_hash(stored_password):
        legacy_hash = hashlib.sha256(supplied_password.encode("utf-8")).hexdigest()
        return legacy_hash == stored_password

    try:
        return check_password_hash(stored_password, supplied_password)
    except (ValueError, TypeError):
        return False
