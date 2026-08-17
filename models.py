# models.py
import os
import sqlite3
from datetime import datetime
import hashlib
import bcrypt

# ===== استخدام Persistent Storage =====
DB_PATH = '/app/data/tasks.db'

# ===== لو على جهاز محلي =====
if not os.path.exists('/app/data'):
    DB_PATH = 'tasks.db'

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=10000')
    conn.execute('PRAGMA busy_timeout=30000')
    return conn

def hash_password(password):
    """تشفير كلمة المرور باستخدام bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password, hashed):
    """التحقق من كلمة المرور"""
    return hashlib.sha256(password.encode()).hexdigest() == hashed

def get_user_permissions(user_id):
    """جلب جميع صلاحيات المستخدم (من دوره + صلاحياته الخاصة)"""
    conn = get_db()
    cursor = conn.cursor()
    
    # صلاحيات من الدور
    cursor.execute("""
        SELECT DISTINCT p.name
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN users u ON u.id = ?
        WHERE u.id = ?
    """, (user_id, user_id))
    
    permissions = {row[0] for row in cursor.fetchall()}
    
    # صلاحيات إضافية من user_permissions
    cursor.execute("""
        SELECT p.name
        FROM permissions p
        JOIN user_permissions up ON p.id = up.permission_id
        WHERE up.user_id = ?
    """, (user_id,))
    
    for row in cursor.fetchall():
        permissions.add(row[0])
    
    conn.close()
    return permissions

def has_permission(user_id, permission_name):
    """التحقق من وجود صلاحية معينة للمستخدم"""
    permissions = get_user_permissions(user_id)
    return permission_name in permissions

def add_permission_to_user(user_id, permission_name):
    """إضافة صلاحية معينة للمستخدم"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM permissions WHERE name = ?", (permission_name,))
    perm = cursor.fetchone()
    if perm:
        cursor.execute("""
            INSERT OR IGNORE INTO user_permissions (user_id, permission_id)
            VALUES (?, ?)
        """, (user_id, perm[0]))
        conn.commit()
    
    conn.close()

def remove_permission_from_user(user_id, permission_name):
    """إزالة صلاحية معينة من المستخدم"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM permissions WHERE name = ?", (permission_name,))
    perm = cursor.fetchone()
    if perm:
        cursor.execute("""
            DELETE FROM user_permissions
            WHERE user_id = ? AND permission_id = ?
        """, (user_id, perm[0]))
        conn.commit()
    
    conn.close()

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
            address TEXT,
            company_name TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS client_trainers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            trainer_id INTEGER NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
            FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE CASCADE,
            UNIQUE(client_id, trainer_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            created_by INTEGER,
            assigned_user_id INTEGER,
            trainer_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT CHECK(status IN ('لم تبدأ', 'قيد التنفيذ', 'مراجعة', 'مكتملة', 'متأخرة')) DEFAULT 'لم تبدأ',
            priority TEXT CHECK(priority IN ('منخفضة', 'متوسطة', 'عالية')) DEFAULT 'متوسطة',
            due_date DATE NOT NULL,
            completion_percentage INTEGER DEFAULT 0,
            task_group TEXT,
            meeting_id INTEGER,
            estimated_duration INTEGER DEFAULT 0,
            actual_duration INTEGER DEFAULT 0,
            contract_payment_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (assigned_user_id) REFERENCES users(id),
            FOREIGN KEY (trainer_id) REFERENCES trainers(id),
            FOREIGN KEY (meeting_id) REFERENCES meetings(id),
            FOREIGN KEY (contract_payment_id) REFERENCES contract_payments(id)
        )
    """)
    
    cursor.execute("""
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
    """)
    
    cursor.execute("""
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
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            meeting_date DATETIME NOT NULL,
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
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meeting_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            reminder_time DATETIME NOT NULL,
            sent INTEGER DEFAULT 0,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS module_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contract_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id INTEGER NOT NULL,
            module_type_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            price REAL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contract_id) REFERENCES client_contracts(id) ON DELETE CASCADE,
            FOREIGN KEY (module_type_id) REFERENCES module_types(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS client_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS client_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_installments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER NOT NULL,
            installment_number INTEGER NOT NULL,
            amount REAL NOT NULL,
            due_date DATE NOT NULL,
            status TEXT CHECK(status IN ('مستحق', 'مدفوع', 'متأخر')) DEFAULT 'مستحق',
            paid_date DATE,
            notes TEXT,
            FOREIGN KEY (payment_id) REFERENCES client_payments(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ip_address TEXT,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contract_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS client_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            contract_type_id INTEGER,
            contract_number TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            contract_value REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            paid_amount REAL DEFAULT 0,
            payment_status TEXT CHECK(payment_status IN ('غير مدفوع', 'مدفوع جزئيا', 'مدفوع بالكامل')) DEFAULT 'غير مدفوع',
            status TEXT CHECK(status IN ('نشط', 'منتهي', 'ملغي', 'معلق')) DEFAULT 'نشط',
            file_path TEXT,
            notes TEXT,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
            FOREIGN KEY (contract_type_id) REFERENCES contract_types(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contract_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id INTEGER NOT NULL,
            installment_number INTEGER NOT NULL,
            amount REAL NOT NULL,
            paid_amount REAL DEFAULT 0,
            due_date DATE NOT NULL,
            payment_date DATE,
            status TEXT CHECK(status IN ('مستحقة', 'مدفوعة', 'مدفوعة جزئيا', 'متأخرة')) DEFAULT 'مستحقة',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contract_id) REFERENCES client_contracts(id) ON DELETE CASCADE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contract_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            file_type TEXT,
            uploaded_by INTEGER NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contract_id) REFERENCES client_contracts(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        )
    """)
    
    # ===== جدول الصلاحيات =====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            resource TEXT NOT NULL,
            action TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            is_default INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
            FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE,
            UNIQUE(role_id, permission_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            granted_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE,
            FOREIGN KEY (granted_by) REFERENCES users(id),
            UNIQUE(user_id, permission_id)
        )
    """)
    
    # ===== ترقية جدول tasks =====
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN created_by INTEGER")
        print("✅ تم إضافة عمود created_by")
    except sqlite3.OperationalError:
        print("ℹ️ عمود created_by موجود مسبقاً")
    
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN assigned_user_id INTEGER")
        print("✅ تم إضافة عمود assigned_user_id")
    except sqlite3.OperationalError:
        print("ℹ️ عمود assigned_user_id موجود مسبقاً")
    
    try:
        cursor.execute("ALTER TABLE tasks RENAME COLUMN assigned_to TO trainer_id")
        print("✅ تم تغيير اسم العمود إلى trainer_id")
    except sqlite3.OperationalError:
        print("ℹ️ عمود trainer_id موجود مسبقاً")
    
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN contract_payment_id INTEGER")
        print("✅ تم إضافة عمود contract_payment_id إلى جدول tasks")
    except sqlite3.OperationalError:
        print("ℹ️ عمود contract_payment_id موجود مسبقاً")
    
    try:
        cursor.execute("ALTER TABLE company_settings ADD COLUMN favicon_path TEXT")
        print("✅ تم إضافة عمود favicon_path")
    except sqlite3.OperationalError:
        print("ℹ️ عمود favicon_path موجود مسبقاً")
    
    # ===== الصلاحيات الافتراضية =====
    default_permissions = [
        ('tasks.view', 'tasks', 'view', 'عرض المهام'),
        ('tasks.create', 'tasks', 'create', 'إنشاء مهام'),
        ('tasks.edit', 'tasks', 'edit', 'تعديل المهام'),
        ('tasks.delete', 'tasks', 'delete', 'حذف المهام'),
        ('tasks.assign', 'tasks', 'assign', 'تعيين المهام'),
        ('clients.view', 'clients', 'view', 'عرض العملاء'),
        ('clients.create', 'clients', 'create', 'إنشاء عملاء'),
        ('clients.edit', 'clients', 'edit', 'تعديل العملاء'),
        ('clients.delete', 'clients', 'delete', 'حذف العملاء'),
        ('contracts.view', 'contracts', 'view', 'عرض العقود'),
        ('contracts.create', 'contracts', 'create', 'إنشاء عقود'),
        ('contracts.edit', 'contracts', 'edit', 'تعديل العقود'),
        ('payments.view', 'payments', 'view', 'عرض المدفوعات'),
        ('payments.create', 'payments', 'create', 'إنشاء مدفوعات'),
        ('payments.edit', 'payments', 'edit', 'تعديل المدفوعات'),
        ('reports.view', 'reports', 'view', 'عرض التقارير'),
        ('reports.export', 'reports', 'export', 'تصدير التقارير'),
        ('users.view', 'users', 'view', 'عرض المستخدمين'),
        ('users.create', 'users', 'create', 'إنشاء مستخدمين'),
        ('users.edit', 'users', 'edit', 'تعديل المستخدمين'),
        ('users.delete', 'users', 'delete', 'حذف المستخدمين'),
    ]
    
    for perm_name, resource, action, description in default_permissions:
        cursor.execute("""
            INSERT OR IGNORE INTO permissions (name, resource, action, description)
            VALUES (?, ?, ?, ?)
        """, (perm_name, resource, action, description))
    
    # ===== الأدوار الافتراضية =====
    default_roles = [
        ('مدير', 'مدير النظام - لديه جميع الصلاحيات', 0),
        ('موظف', 'موظف عادي - صلاحيات محدودة', 1),
        ('مراقب', 'مشاهد - صلاحيات عرض فقط', 0),
    ]
    
    for role_name, description, is_default in default_roles:
        cursor.execute("""
            INSERT OR IGNORE INTO roles (name, description, is_default)
            VALUES (?, ?, ?)
        """, (role_name, description, is_default))
    
    # ===== ربط الأدوار بالصلاحيات =====
    roles_map = {}
    cursor.execute("SELECT id, name FROM roles")
    for row in cursor.fetchall():
        roles_map[row[1]] = row[0]
    
    perms_map = {}
    cursor.execute("SELECT id, name FROM permissions")
    for row in cursor.fetchall():
        perms_map[row[1]] = row[0]
    
    # صلاحيات المدير
    if 'مدير' in roles_map:
        for perm_id in perms_map.values():
            cursor.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                VALUES (?, ?)
            """, (roles_map['مدير'], perm_id))
    
    # صلاحيات الموظف
    if 'موظف' in roles_map:
        employee_perms = [
            'tasks.view', 'tasks.create', 'tasks.edit', 'tasks.assign',
            'clients.view', 'clients.create', 'clients.edit',
            'contracts.view', 'contracts.create',
            'payments.view', 'payments.create',
            'reports.view'
        ]
        for perm_name in employee_perms:
            if perm_name in perms_map:
                cursor.execute("""
                    INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                    VALUES (?, ?)
                """, (roles_map['موظف'], perms_map[perm_name]))
    
    # صلاحيات المراقب
    if 'مراقب' in roles_map:
        viewer_perms = [
            'tasks.view', 'clients.view', 'contracts.view',
            'payments.view', 'reports.view', 'users.view'
        ]
        for perm_name in viewer_perms:
            if perm_name in perms_map:
                cursor.execute("""
                    INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                    VALUES (?, ?)
                """, (roles_map['مراقب'], perms_map[perm_name]))
    
    # ===== البيانات الافتراضية =====
    cursor.execute("SELECT * FROM company_settings")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO company_settings (name, name_en, phone, address, email, website)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('شركة التقنية المتقدمة', 'Advanced Technology Company', '+966 50 123 4567', 'الرياض، المملكة العربية السعودية', 'info@techcompany.com', 'www.techcompany.com'))
    
    cursor.execute("SELECT * FROM users WHERE username = 'Adminerp'")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO users (username, name, email, password, role)
            VALUES (?, ?, ?, ?, ?)
        """, ('Adminerp', 'مدير النظام', 'adminerp@company.com', hash_password('1234'), 'مدير'))
    
    cursor.execute("SELECT * FROM users WHERE username = 'Fahd01'")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO users (username, name, email, password, role)
            VALUES (?, ?, ?, ?, ?)
        """, ('Fahd01', 'فهد المدير', 'fahd@company.com', hash_password('1234'), 'مدير'))
    
    cursor.execute("SELECT * FROM users WHERE username = 'employee1'")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO users (username, name, email, password, role)
            VALUES 
            ('employee1', 'سارة موظف', 'sara@company.com', ?, 'موظف'),
            ('viewer1', 'خالد مراقب', 'khalid@company.com', ?, 'مراقب')
        """, (hash_password('1234'), hash_password('1234')))
    
    # ===== المدربين الافتراضيين =====
    cursor.execute("SELECT COUNT(*) as count FROM trainers")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO trainers (name, phone, email, specialty, notes, is_active)
            VALUES 
            ('أحمد سليمان', '0551234567', 'ahmed@trainer.com', 'تدريب تقني', 'مدرب معتمد', 1),
            ('نورة القحطاني', '0552345678', 'noura@trainer.com', 'مهارات قيادية', 'مدربة معتمدة', 1),
            ('خالد المالكي', '0553456789', 'khalid@trainer.com', 'تطوير برمجيات', 'متخصص في التطوير', 1)
        """)
    
    # ===== أنواع العقود الافتراضية =====
    cursor.execute("SELECT COUNT(*) as count FROM contract_types")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO contract_types (name, description)
            VALUES 
            ('عقد خدمات', 'عقد تقديم خدمات استشارية أو تقنية'),
            ('عقد مقاولات', 'عقد أعمال مقاولات وإنشاءات'),
            ('عقد توريد', 'عقد توريد مواد أو معدات'),
            ('عقد تدريب', 'عقد تقديم دورات تدريبية')
        """)
    
    # ===== أنواع المديولات الافتراضية =====
    cursor.execute("SELECT COUNT(*) as count FROM module_types")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO module_types (name, description, price)
            VALUES 
            ('نظام إدارة الموارد البشرية', 'نظام متكامل لإدارة الموظفين والرواتب', 15000),
            ('نظام المحاسبة', 'نظام محاسبي متكامل مع التقارير المالية', 20000),
            ('نظام إدارة العملاء CRM', 'نظام لإدارة علاقات العملاء والمبيعات', 12000),
            ('نظام إدارة المشاريع', 'نظام لتخطيط ومتابعة المشاريع', 18000),
            ('نظام نقاط البيع POS', 'نظام نقاط بيع متكامل مع المخزون', 10000)
        """)
    
    conn.commit()
    print(f"✅ تم تهيئة قاعدة البيانات في: {DB_PATH}")
    conn.close()

# ===== استدعاء التهيئة =====
init_db()