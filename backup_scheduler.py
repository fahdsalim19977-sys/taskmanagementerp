# backup_scheduler.py
import os
import shutil
import sqlite3
import datetime
import time
import schedule
import logging

# ===== إعدادات التسجيل =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backup.log'),
        logging.StreamHandler()
    ]
)

DB_PATH = '/app/data/tasks.db'
BACKUP_DIR = '/app/data/backups/'
MAX_BACKUPS = 30  # الاحتفاظ بآخر 30 نسخة

def create_backup():
    """إنشاء نسخة احتياطية"""
    try:
        # التأكد من وجود مجلد النسخ الاحتياطي
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # اسم الملف مع التاريخ
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_{timestamp}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        
        # نسخ قاعدة البيانات
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, backup_path)
            logging.info(f"✅ تم إنشاء النسخة الاحتياطية: {backup_name}")
            
            # تصدير SQL أيضاً
            sql_path = backup_path.replace('.db', '.sql')
            conn = sqlite3.connect(DB_PATH)
            with open(sql_path, 'w', encoding='utf-8') as f:
                for line in conn.iterdump():
                    f.write('%s\n' % line)
            conn.close()
            logging.info(f"✅ تم تصدير SQL: {sql_path}")
            
            # حذف النسخ القديمة
            clean_old_backups()
        else:
            logging.error("❌ قاعدة البيانات غير موجودة")
    except Exception as e:
        logging.error(f"❌ خطأ في إنشاء النسخة الاحتياطية: {str(e)}")

def clean_old_backups():
    """حذف النسخ الاحتياطية القديمة"""
    try:
        files = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')])
        if len(files) > MAX_BACKUPS:
            for f in files[:-MAX_BACKUPS]:
                os.remove(os.path.join(BACKUP_DIR, f))
                # حذف ملف SQL المرتبط
                sql_file = f.replace('.db', '.sql')
                if os.path.exists(os.path.join(BACKUP_DIR, sql_file)):
                    os.remove(os.path.join(BACKUP_DIR, sql_file))
            logging.info(f"🗑️ تم حذف {len(files) - MAX_BACKUPS} نسخة قديمة")
    except Exception as e:
        logging.error(f"❌ خطأ في حذف النسخ القديمة: {str(e)}")

def run_scheduler():
    """تشغيل الجدولة"""
    # جدولة النسخ الاحتياطي كل 24 ساعة
    schedule.every(24).hours.do(create_backup)
    
    # عمل نسخة فورية عند بدء التشغيل
    create_backup()
    
    logging.info("🚀 بدء تشغيل جدولة النسخ الاحتياطي (كل 24 ساعة)")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # التحقق كل دقيقة

if __name__ == '__main__':
    run_scheduler()