# models.py
import os
import sqlite3
from datetime import datetime
import hashlib
import bcrypt

# ===== استخدام Persistent Storage =====
DB_PATH = '/app/data/tasks.db'

# ===== لو على جهاز محلي =====
if not os.path.exists('/app/data'):
    DB_PATH = 'tasks.db'

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=10000')
    conn.execute('PRAGMA busy_timeout=30000')
    return conn

def hash_password(password):
    """Hash passwords using bcrypt."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """Verify bcrypt hashes and safely recognize legacy SHA-256 hashes.

    Legacy hashes are accepted only for authentication compatibility. The login
    layer should replace a successful legacy hash with hash_password(password).
    """
    if not isinstance(password, str) or not isinstance(hashed, str) or not hashed:
        return False

    try:
        if hashed.startswith(('$2a$', '$2b$', '$2y$')):
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

        # Legacy SHA-256 migration path.
        if len(hashed) == 64:
            return hashlib.sha256(password.encode('utf-8')).hexdigest() == hashed
    except (ValueError, TypeError):
        return False

    return False

def get_user_permissions(user_id):
    """جلب جميع صلاحيات المستخدم (من دوره + صلاحياته الخاصة)"""
    conn = get_db()
    cursor = conn.cursor()
    
    # صلاحيات من الدور
    cursor.execute("""
        SELECT DISTINCT p.name
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN users u ON u.id = ?
        WHERE u.id = ?
    """, (user_id, user_id))
    
    permissions = {row[0] for row in cursor.fetchall()}
    
    # صلاحيات إضافية من user_permissions
