# migrate_contracts.py
import sqlite3
import os

DB_PATH = '/app/data/tasks.db'

# لو على جهاز محلي
if not os.path.exists('/app/data'):
    DB_PATH = 'tasks.db'

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. إضافة عمود contract_type_id
    try:
        cursor.execute("ALTER TABLE client_contracts ADD COLUMN contract_type_id INTEGER")
        print("✅ تم إضافة عمود contract_type_id")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ عمود contract_type_id موجود مسبقاً")
        else:
            print(f"❌ خطأ: {e}")
    
    # 2. إضافة عمود total_amount
    try:
        cursor.execute("ALTER TABLE client_contracts ADD COLUMN total_amount REAL DEFAULT 0")
        print("✅ تم إضافة عمود total_amount")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ عمود total_amount موجود مسبقاً")
        else:
            print(f"❌ خطأ: {e}")
    
    # 3. إضافة عمود paid_amount
    try:
        cursor.execute("ALTER TABLE client_contracts ADD COLUMN paid_amount REAL DEFAULT 0")
        print("✅ تم إضافة عمود paid_amount")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ عمود paid_amount موجود مسبقاً")
        else:
            print(f"❌ خطأ: {e}")
    
    # 4. إضافة عمود payment_status
    try:
        cursor.execute("ALTER TABLE client_contracts ADD COLUMN payment_status TEXT DEFAULT 'غير مدفوع'")
        print("✅ تم إضافة عمود payment_status")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ عمود payment_status موجود مسبقاً")
        else:
            print(f"❌ خطأ: {e}")
    
    # 5. إنشاء جدول contract_payments
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contract_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                installment_number INTEGER NOT NULL,
                amount REAL NOT NULL,
                paid_amount REAL DEFAULT 0,
                due_date DATE NOT NULL,
                payment_date DATE,
                status TEXT DEFAULT 'مستحقة',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES client_contracts(id) ON DELETE CASCADE
            )
        ''')
        print("✅ تم إنشاء جدول contract_payments")
    except sqlite3.OperationalError as e:
        print(f"ℹ️ {e}")
    
    # 6. إنشاء جدول contract_attachments
    try:
        cursor.execute('''
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
        ''')
        print("✅ تم إنشاء جدول contract_attachments")
    except sqlite3.OperationalError as e:
        print(f"ℹ️ {e}")
    
    # 7. إنشاء جدول contract_types
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contract_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ تم إنشاء جدول contract_types")
    except sqlite3.OperationalError as e:
        print(f"ℹ️ {e}")
    
    conn.commit()
    conn.close()
    print("🎉 تم ترقية قاعدة البيانات بنجاح!")

if __name__ == '__main__':
    migrate()