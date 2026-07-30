# clear_payments.py
import sqlite3

DB_NAME = 'tasks.db'

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# مسح المدفوعات
cursor.execute('DELETE FROM client_payments')
cursor.execute('DELETE FROM payment_installments')

# إعادة ضبط الـ Auto-increment
cursor.execute("DELETE FROM sqlite_sequence WHERE name='client_payments'")
cursor.execute("DELETE FROM sqlite_sequence WHERE name='payment_installments'")

conn.commit()
conn.close()

print('✅ تم مسح جميع المدفوعات بنجاح!')