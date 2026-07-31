# models.py
import os
import sqlite3
from datetime import datetime
import hashlib

# ===== استخدام Persistent Storage =====
DB_PATH = '/app/data/tasks.db'

# ===== لو على جهاز محلي =====
if not os.path.exists('/app/data'):
    DB_PATH = 'tasks.db'

def get_db():
    # تأكد من وجود المجلد
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # ===== جدول إعدادات الشركة =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS company_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            name_en TEXT,
            phone TEXT,
            address TEXT,
            logo_path TEXT,
            email TEXT,
            website TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ===== جدول المستخدمين =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT CHECK(role IN ("مدير", "موظف", "مراقب")) NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ===== جدول المدربين =====
    cursor.execute('''
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
    ''')
    
    # ===== جدول العملاء =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT,
            company_name TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ===== جدول ربط العملاء بالمدربين =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS client_trainers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            trainer_id INTEGER NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
            FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE CASCADE,
            UNIQUE(client_id, trainer_id)
        )
    ''')
    
    # ===== جدول المهام (التدريبات) =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            assigned_to INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT CHECK(status IN ("لم تبدأ", "قيد التنفيذ", "مكتملة", "متأخرة")) DEFAULT "لم تبدأ",
            priority TEXT CHECK(priority IN ("منخفضة", "متوسطة", "عالية")) DEFAULT "متوسطة",
            due_date DATE NOT NULL,
            completion_percentage INTEGER DEFAULT 0,
            task_group TEXT,
            meeting_id INTEGER,
            estimated_duration INTEGER DEFAULT 0,
            actual_duration INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (assigned_to) REFERENCES users(id),
            FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        )
    ''')
    
    # ===== جدول ملاحظات المهام =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            note TEXT,
            attachment_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # ===== جدول الإشعارات =====
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
    
    # ===== جدول سجل النشاط =====
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
    
    # ===== جدول المواعيد =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            meeting_date DATETIME NOT NULL,
            duration INTEGER DEFAULT 60,
            location TEXT,
            meeting_link TEXT,
            status TEXT CHECK(status IN ("مجدول", "تم", "ملغي")) DEFAULT "مجدول",
            reminder_sent INTEGER DEFAULT 0,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # ===== جدول تذكيرات المواعيد =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meeting_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            reminder_time DATETIME NOT NULL,
            sent INTEGER DEFAULT 0,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        )
    ''')
    
    # ===== جدول المديولات =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS client_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            price REAL DEFAULT 0,
            status TEXT CHECK(status IN ("نشط", "قيد التطوير", "مكتمل", "متوقف")) DEFAULT "نشط",
            start_date DATE,
            end_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    ''')
    
    # ===== جدول المدفوعات =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS client_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            module_id INTEGER,
            amount REAL NOT NULL,
            payment_date DATE NOT NULL,
            due_date DATE,
            payment_method TEXT CHECK(payment_method IN ("نقدي", "تحويل بنكي", "شيك", "بطاقة ائتمان", "أخرى")) DEFAULT "نقدي",
            status TEXT CHECK(status IN ("مدفوع", "معلق", "متأخر")) DEFAULT "معلق",
            invoice_number TEXT,
            notes TEXT,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (module_id) REFERENCES client_modules(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # ===== جدول دفعات المدفوعات =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_installments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER NOT NULL,
            installment_number INTEGER NOT NULL,
            amount REAL NOT NULL,
            due_date DATE NOT NULL,
            status TEXT CHECK(status IN ("مستحق", "مدفوع", "متأخر")) DEFAULT "مستحق",
            paid_date DATE,
            notes TEXT,
            FOREIGN KEY (payment_id) REFERENCES client_payments(id)
        )
    ''')
    
    # ===== جدول محاولات تسجيل الدخول =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ip_address TEXT,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 0
        )
    ''')
    
    # ===== إعدادات الشركة =====
    cursor.execute("SELECT * FROM company_settings")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO company_settings (name, name_en, phone, address, email, website)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('شركة التقنية المتقدمة', 'Advanced Technology Company', '+966 50 123 4567', 'الرياض، المملكة العربية السعودية', 'info@techcompany.com', 'www.techcompany.com'))
    
    # ===== إضافة المستخدمين =====
    cursor.execute("SELECT * FROM users WHERE username = 'Fahd01'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (username, name, email, password, role)
            VALUES (?, ?, ?, ?, ?)
        ''', ('Fahd01', 'فهد المدير', 'fahd@company.com', hash_password('1234'), 'مدير'))
    
    cursor.execute("SELECT * FROM users WHERE username = 'Adminerp'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (username, name, email, password, role)
            VALUES (?, ?, ?, ?, ?)
        ''', ('Adminerp', 'مدير النظام', 'adminerp@company.com', hash_password('1234'), 'مدير'))
    
    cursor.execute("SELECT * FROM users WHERE username = 'employee1'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (username, name, email, password, role)
            VALUES 
            ('employee1', 'سارة موظف', 'sara@company.com', ?, 'موظف'),
            ('viewer1', 'خالد مراقب', 'khalid@company.com', ?, 'مراقب')
        ''', (hash_password('1234'), hash_password('1234')))
    
    # ===== إضافة مدربين تجريبيين (لو مفيش) =====
    cursor.execute("SELECT COUNT(*) as count FROM trainers")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO trainers (name, phone, email, specialty, notes)
            VALUES 
            ('أحمد سليمان', '0551234567', 'ahmed@trainer.com', 'تدريب تقني', 'مدرب معتمد'),
            ('نورة القحطاني', '0552345678', 'noura@trainer.com', 'مهارات قيادية', 'مدربة معتمدة'),
            ('خالد المالكي', '0553456789', 'khalid@trainer.com', 'تطوير برمجيات', 'متخصص في التطوير')
        ''')
        print("✅ تم إضافة مدربين تجريبيين")
    
    conn.commit()
    print(f"✅ تم تهيئة قاعدة البيانات في: {DB_PATH}")
    conn.close()
