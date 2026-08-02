# models.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import hashlib
from config import Config

# ============================================================
# الاتصال بقاعدة البيانات
# ============================================================

def get_db():
    try:
        conn = psycopg2.connect(Config.DATABASE_URL)
        conn.cursor_factory = RealDictCursor
        return conn
    except Exception as e:
        print(f"❌ خطأ: {str(e)}")
        return None

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = get_db()
    if not conn:
        print("❌ فشل الاتصال بقاعدة البيانات")
        return
    
    cursor = conn.cursor()
    
    # ===== جميع الجداول (PostgreSQL) =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS company_settings (
            id SERIAL PRIMARY KEY,
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT CHECK(role IN ('مدير', 'موظف', 'مراقب')) NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trainers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            specialty TEXT,
            notes TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT,
            company_name TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS client_trainers (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            trainer_id INTEGER NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
            FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE CASCADE,
            UNIQUE(client_id, trainer_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            assigned_to INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT CHECK(status IN ('لم تبدأ', 'قيد التنفيذ', 'مكتملة', 'متأخرة')) DEFAULT 'لم تبدأ',
            priority TEXT CHECK(priority IN ('منخفضة', 'متوسطة', 'عالية')) DEFAULT 'متوسطة',
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_updates (
            id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            note TEXT,
            attachment_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            task_id INTEGER,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meetings (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            meeting_date TIMESTAMP NOT NULL,
            duration INTEGER DEFAULT 60,
            location TEXT,
            meeting_link TEXT,
            status TEXT CHECK(status IN ('مجدول', 'تم', 'ملغي')) DEFAULT 'مجدول',
            reminder_sent INTEGER DEFAULT 0,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meeting_reminders (
            id SERIAL PRIMARY KEY,
            meeting_id INTEGER NOT NULL,
            reminder_time TIMESTAMP NOT NULL,
            sent INTEGER DEFAULT 0,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS client_modules (
            id SERIAL PRIMARY KEY,
            client_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            price REAL DEFAULT 0,
            status TEXT CHECK(status IN ('نشط', 'قيد التطوير', 'مكتمل', 'متوقف')) DEFAULT 'نشط',
            start_date DATE,
            end_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS client_payments (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            module_id INTEGER,
            amount REAL NOT NULL,
            payment_date DATE NOT NULL,
            due_date DATE,
            payment_method TEXT CHECK(payment_method IN ('نقدي', 'تحويل بنكي', 'شيك', 'بطاقة ائتمان', 'أخرى')) DEFAULT 'نقدي',
            status TEXT CHECK(status IN ('مدفوع', 'معلق', 'متأخر')) DEFAULT 'معلق',
            invoice_number TEXT,
            notes TEXT,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (module_id) REFERENCES client_modules(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_installments (
            id SERIAL PRIMARY KEY,
            payment_id INTEGER NOT NULL,
            installment_number INTEGER NOT NULL,
            amount REAL NOT NULL,
            due_date DATE NOT NULL,
            status TEXT CHECK(status IN ('مستحق', 'مدفوع', 'متأخر')) DEFAULT 'مستحق',
            paid_date DATE,
            notes TEXT,
            FOREIGN KEY (payment_id) REFERENCES client_payments(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS login_attempts (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            ip_address TEXT,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS client_contracts (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            contract_number TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            contract_value REAL DEFAULT 0,
            status TEXT CHECK(status IN ('نشط', 'منتهي', 'ملغي', 'معلق')) DEFAULT 'نشط',
            file_path TEXT,
            notes TEXT,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # ============================================================
    # البيانات الافتراضية
    # ============================================================
    
    cursor.execute("SELECT * FROM company_settings")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO company_settings (name, name_en, phone, address, email, website)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', ('شركة التقنية المتقدمة', 'Advanced Technology Company', '+966 50 123 4567', 'الرياض، المملكة العربية السعودية', 'info@techcompany.com', 'www.techcompany.com'))
    
    cursor.execute("SELECT * FROM users WHERE username = 'Adminerp'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (username, name, email, password, role)
            VALUES (%s, %s, %s, %s, %s)
        ''', ('Adminerp', 'مدير النظام', 'adminerp@company.com', hash_password('1234'), 'مدير'))
    
    conn.commit()
    print("✅ تم تهيئة قاعدة البيانات بنجاح!")
    conn.close()
