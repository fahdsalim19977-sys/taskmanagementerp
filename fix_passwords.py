# fix_passwords.py
import sqlite3
import bcrypt

def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

# ===== تحديث كلمات المرور =====
DB_PATH = '/app/data/tasks.db'

def fix_passwords():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # جلب جميع المستخدمين
    users = cursor.execute("SELECT id, username, password FROM users").fetchall()
    
    updated = 0
    for user in users:
        user_id, username, password = user
        
        # إذا كانت كلمة المرور ليست bcrypt (لا تبدأ بـ $2b$)
        if not password.startswith('$2b$'):
            print(f"🔑 تحديث كلمة مرور المستخدم: {username}")
            new_hash = hash_password('1234')  # استخدام 1234 ككلمة مرور افتراضية
            cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_hash, user_id))
            updated += 1
    
    conn.commit()
    conn.close()
    print(f"✅ تم تحديث {updated} مستخدم")

if __name__ == '__main__':
    fix_passwords()