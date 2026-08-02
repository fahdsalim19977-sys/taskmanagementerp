# config.py
import os

class Config:
    SECRET_KEY = 'your_secret_key_here_change_in_production'
    
    # ===== قاعدة بيانات SQLite =====
    DB_PATH = os.environ.get('DB_PATH', 'tasks.db')  # استخدم متغير بيئة أو المسار الافتراضي
    
    # ===== إعدادات أخرى =====
    UPLOAD_FOLDER = 'uploads/'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'your_email@gmail.com'
    MAIL_PASSWORD = 'your_app_password'
    MAIL_DEFAULT_SENDER = 'your_email@gmail.com'
    
    COMPANY_NAME = 'شركة التقنية المتقدمة'
    COMPANY_NAME_EN = 'Advanced Technology Company'
    COMPANY_PHONE = '+966 50 123 4567'
    COMPANY_ADDRESS = 'الرياض، المملكة العربية السعودية'
    COMPANY_LOGO = 'logo.png'
    
    DEFAULT_USERNAME = 'Fahd01'
    DEFAULT_PASSWORD = '1234'
