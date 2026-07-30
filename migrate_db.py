# migrate_db.py
import sqlite3
import hashlib

DB_NAME = 'tasks.db'

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def migrate():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # 1. إضافة عمود username للمستخدمين
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT UNIQUE")
        print("✅ أضفنا عمود username")
    except sqlite3.OperationalError:
        print("ℹ️ عمود username موجود مسبقاً")
    
    try:
        # 2. إضافة عمود is_active
        cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
        print("✅ أضفنا عمود is_active")
    except sqlite3.OperationalError:
        print("ℹ️ عمود is_active موجود مسبقاً")
    
    try:
        # 3. تحديث المستخدمين الحاليين - إضافة username مؤقت
        cursor.execute("UPDATE users SET username = email WHERE username IS NULL")
        print("✅ حدثنا usernames")
    except:
        pass
    
    try:
        # 4. إنشاء جدول company_settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS company_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                address TEXT,
                logo_path TEXT,
                email TEXT,
                website TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ أنشأنا جدول company_settings")
    except:
        pass
    
    try:
        # 5. إنشاء جدول notifications
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id INTEGER,
                message TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        ''')
        print("✅ أنشأنا جدول notifications")
    except:
        pass
    
    try:
        # 6. إنشاء جدول activity_log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        print("✅ أنشأنا جدول activity_log")
    except:
        pass
    
    # 7. تحديث العملاء - إضافة أعمدة جديدة
    try:
        cursor.execute("ALTER TABLE clients ADD COLUMN company_name TEXT")
        print("✅ أضفنا company_name للعملاء")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE clients ADD COLUMN notes TEXT")
        print("✅ أضفنا notes للعملاء")
    except:
        pass
    
    # 8. إضافة مستخدم Fahd01
    cursor.execute("SELECT * FROM users WHERE email = 'fahd@company.com'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (username, name, email, password, role)
            VALUES (?, ?, ?, ?, ?)
        ''', ('Fahd01', 'فهد المدير', 'fahd@company.com', hash_password('1234'), 'مدير'))
        print("✅ أضفنا مستخدم Fahd01")
    
    # 9. إعدادات الشركة الافتراضية
    cursor.execute("SELECT * FROM company_settings")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO company_settings (name, phone, address, email, website)
            VALUES (?, ?, ?, ?, ?)
        ''', ('شركة التقنية المتقدمة', '+966 50 123 4567', 'الرياض، المملكة العربية السعودية', 'info@techcompany.com', 'www.techcompany.com'))
        print("✅ أضفنا إعدادات الشركة")
    
    conn.commit()
    conn.close()
    print("🎉 تم ترقية قاعدة البيانات بنجاح!")

if __name__ == '__main__':
    migrate()
