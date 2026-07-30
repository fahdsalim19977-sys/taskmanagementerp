# reset_password.py
import sqlite3
import hashlib

DB_NAME = 'tasks.db'

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# ===== تغيير كلمة المرور لجميع المستخدمين إلى 1234 =====
new_password = hash_password('1234')

cursor.execute("UPDATE users SET password = ?", (new_password,))

conn.commit()

# ===== عرض المستخدمين =====
users = cursor.execute("SELECT id, username, role FROM users").fetchall()

print("✅ تم تغيير كلمة المرور لجميع المستخدمين إلى: 1234")
print("")
print("🔑 حسابات الدخول:")
for user in users:
    print(f"   {user[1]} / 1234 ({user[2]})")

conn.close()