# utils.py
from models import get_db
from flask import session
import time
import sqlite3

def log_activity(user_id, action, details=None, retries=5):
    """تسجيل النشاط مع إعادة المحاولة في حالة القفل"""
    for attempt in range(retries):
        conn = None
        try:
            conn = get_db()
            # ✅ إضافة busy_timeout
            conn.execute('PRAGMA busy_timeout = 5000')
            # ✅ استخدام BEGIN IMMEDIATE لتجنب القفل
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)', 
                         (user_id, action, details))
            conn.commit()
            conn.close()
            return True
        except sqlite3.OperationalError as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            if "database is locked" in str(e) and attempt < retries - 1:
                wait_time = 0.5 * (attempt + 1)
                print(f"⚠️ قاعدة البيانات مقفلة، محاولة {attempt + 1}/{retries} بعد {wait_time} ثانية")
                time.sleep(wait_time)
                continue
            else:
                print(f"❌ خطأ في تسجيل النشاط: {e}")
                return False
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            print(f"❌ خطأ في تسجيل النشاط: {e}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    return False


def check_role(allowed_roles):
    if 'user_id' not in session:
        return False
    conn = get_db()
    conn.execute('PRAGMA busy_timeout = 5000')
    user = conn.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return user and user['role'] in allowed_roles


def get_company_settings():
    conn = get_db()
    conn.execute('PRAGMA busy_timeout = 5000')
    settings = conn.execute('SELECT * FROM company_settings LIMIT 1').fetchone()
    conn.close()
    return settings


def get_trainers():
    conn = get_db()
    conn.execute('PRAGMA busy_timeout = 5000')
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