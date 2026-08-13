# models.py
import os
import sqlite3
from datetime import datetime
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash

# ===== استخدام Persistent Storage =====
DB_PATH = '/app/data/tasks.db'

# ===== لو على جهاز محلي =====
if not os.path.exists('/app/data'):
    DB_PATH = 'tasks.db'

def get_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=10000')
    conn.execute('PRAGMA busy_timeout=30000')
    return conn

def hash_password(password):
    """Hash a new password using Werkzeug's password-specific algorithm."""
    return generate_password_hash(password)

def verify_password(stored_password, supplied_password):
    """Verify modern hashes and transparently recognize legacy SHA-256 hashes."""
    if not stored_password:
        return False
    try:
        if stored_password.startswith(('pbkdf2:', 'scrypt:')):
            return check_password_hash(stored_password, supplied_password)
    except (ValueError, TypeError):
        return False
    # Legacy SHA-256 compatibility. Successful login should migrate the hash.
    legacy_hash = hashlib.sha256(supplied_password.encode()).hexdigest()
    return stored_password == legacy_hash

def is_legacy_password_hash(stored_password):
    return bool(stored_password) and len(stored_password) == 64 and all(c in '0123456789abcdef' for c in stored_password.lower())

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # ===== جميع الجداول =====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            name_en TEXT,
            phone TEXT,
            address TEXT,
            logo_path TEXT,
            favicon_path TEXT,
            email TEXT,
            website TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT CHECK(role IN ('مدير', 'موظف', 'مراقب')) NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trainers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            specialty TEXT,
            notes TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
