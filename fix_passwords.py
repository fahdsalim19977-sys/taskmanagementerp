# fix_passwords.py
import sqlite3
import bcrypt

def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

# ===== تحديث كلمات المرور =====
DB_PATH = '/app/data/tasks.db'

def fix_all_passwords():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # تحديث كل المستخدمين
        users = cursor.execute("SELECT id, username FROM users").fetchall()
        
        for user in users:
            user_id, username = user
            new_hash = hash_password('1234')
            cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_hash, user_id))
            print(f"✅ تم تحديث {username}")
        
        conn.commit()
        conn.close()
        print("✅ تم تحديث جميع المستخدمين")
        
    except Exception as e:
        print(f"❌ خطأ: {e}")

if __name__ == '__main__':
    fix_all_passwords()