# config.py
import os
import secrets


class Config:
    # Never hard-code production secrets in source control.
    # Set SECRET_KEY in the deployment environment for stable sessions.
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

    # ===== قاعدة بيانات SQLite =====
    DB_PATH = os.environ.get('DB_PATH', 'tasks.db')

    # ===== إعدادات أخرى =====
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads/')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

    # ===== Session security =====
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', '0') == '1'
    PERMANENT_SESSION_LIFETIME = int(os.environ.get('SESSION_LIFETIME_SECONDS', 8 * 60 * 60))

    # ===== Mail =====
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', '1') == '1'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME)

    # ===== Company defaults =====
    COMPANY_NAME = os.environ.get('COMPANY_NAME', 'شركة التقنية المتقدمة')
    COMPANY_NAME_EN = os.environ.get('COMPANY_NAME_EN', 'Advanced Technology Company')
    COMPANY_PHONE = os.environ.get('COMPANY_PHONE', '')
    COMPANY_ADDRESS = os.environ.get('COMPANY_ADDRESS', '')
    COMPANY_LOGO = os.environ.get('COMPANY_LOGO', 'logo.png')

    # ===== Initial admin credentials =====
    # These are only configuration hints for first-run/bootstrap code.
    # Do not ship a real default password in source control.
    DEFAULT_USERNAME = os.environ.get('DEFAULT_USERNAME', '')
    DEFAULT_PASSWORD = os.environ.get('DEFAULT_PASSWORD', '')
