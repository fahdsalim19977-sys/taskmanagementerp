# clear_all_data.py
import sqlite3

DB_NAME = 'tasks.db'

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# ===== قائمة الجداول =====
tables = [
    'client_payments',
    'payment_installments',
    'client_trainers',
    'tasks',
    'task_updates',
    'client_modules',
    'meetings',
    'meeting_reminders',
    'notifications',
    'activity_log',
    'clients',
    'trainers'
]

# ===== مسح البيانات =====
for table in tables:
    try:
        cursor.execute(f'DELETE FROM {table}')
        print(f'✅ تم مسح جدول: {table}')
    except sqlite3.OperationalError as e:
        if 'no such table' in str(e):
            print(f'⚠️ الجدول {table} غير موجود')
        else:
            print(f'❌ خطأ في {table}: {e}')

# ===== إعادة ضبط الـ Auto-increment =====
for table in tables:
    try:
        cursor.execute(f'DELETE FROM sqlite_sequence WHERE name="{table}"')
    except:
        pass

conn.commit()
conn.close()

print('')
print('✅ تم مسح جميع البيانات بنجاح!')
print('📌 يمكنك الآن إضافة بيانات حقيقية جديدة')
