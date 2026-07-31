# backup.py
import os
import shutil
import sqlite3
from datetime import datetime

def create_backup():
    """عمل نسخة احتياطية يدوية"""
    try:
        db_path = 'D:/مهام الشركه/tasks.db'  # لو عندك قاعدة بيانات محلية
        
        # لو على السيرفر
        if os.path.exists('/app/data/tasks.db'):
            db_path = '/app/data/tasks.db'
        
        backup_dir = 'D:/مهام الشركه/backups/'
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        
        # نسخ الملف
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
            print(f"✅ تم إنشاء نسخة احتياطية: {backup_name}")
            print(f"📍 المسار: {backup_path}")
            
            # تصدير إلى SQL (للقراءة)
            sql_path = backup_path.replace('.db', '.sql')
            conn = sqlite3.connect(db_path)
            with open(sql_path, 'w', encoding='utf-8') as f:
                for line in conn.iterdump():
                    f.write('%s\n' % line)
            conn.close()
            print(f"✅ تم تصدير SQL: {sql_path}")
        else:
            print("❌ قاعدة البيانات غير موجودة")
    except Exception as e:
        print(f"❌ خطأ: {str(e)}")

if __name__ == '__main__':
    create_backup()
