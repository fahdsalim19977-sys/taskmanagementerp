# utils.py
from models import get_db
from flask import session
import time
import sqlite3

def log_activity(user_id, action, details=None, retries=5):
    """تسجيل النشاط مع إعادة المحاولة في حالة القفل"""
    conn = None
    for attempt in range(retries):
        try:
            conn = get_db()
            conn.execute('PRAGMA busy_timeout = 30000')
            cursor = conn.cursor()
            cursor.execute('BEGIN IMMEDIATE')
            cursor.execute(
                'INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)',
                (user_id, action, details)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        except sqlite3.OperationalError as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
                try:
                    conn.close()
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
                try:
                    conn.close()
                except:
                    pass
            print(f"❌ خطأ في تسجيل النشاط: {e}")
            return False
            
    return False


def check_role(allowed_roles):
    if 'user_id' not in session:
        return False
    conn = get_db()
    conn.execute('PRAGMA busy_timeout = 10000')
    user = conn.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return user and user['role'] in allowed_roles


def get_company_settings():
    conn = get_db()
    conn.execute('PRAGMA busy_timeout = 10000')
    settings = conn.execute('SELECT * FROM company_settings LIMIT 1').fetchone()
    conn.close()
    return settings


def get_trainers():
    """جلب المدربين النشطين فقط"""
    conn = get_db()
    conn.execute('PRAGMA busy_timeout = 10000')
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
    try:
        from translations import get_text
        return get_text(key, get_lang())
    except:
        return key