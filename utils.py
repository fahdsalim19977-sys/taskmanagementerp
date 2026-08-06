# utils.py
from models import get_db
from flask import session

def log_activity(user_id, action, details=None, retries=3):
    import time
    import sqlite3
    for attempt in range(retries):
        try:
            conn = get_db()
            conn.execute('INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)', 
                         (user_id, action, details))
            conn.commit()
            conn.close()
            return True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < retries - 1:
                time.sleep(0.5)
                continue
            else:
                print(f"❌ خطأ في تسجيل النشاط: {e}")
                return False
        except Exception as e:
            print(f"❌ خطأ في تسجيل النشاط: {e}")
            return False
    return False

def check_role(allowed_roles):
    if 'user_id' not in session:
        return False
    conn = get_db()
    user = conn.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return user and user['role'] in allowed_roles

def get_company_settings():
    conn = get_db()
    settings = conn.execute('SELECT * FROM company_settings LIMIT 1').fetchone()
    conn.close()
    return settings

def get_trainers():
    conn = get_db()
    trainers = conn.execute('''
        SELECT id, name FROM trainers 
        WHERE is_active = 1
        ORDER BY name
    ''').fetchall()
    conn.close()
    return trainers

def get_lang():
    return session.get('lang', 'ar')

def t(key):
    from translations import get_text
    return get_text(key, get_lang())