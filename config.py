import os
from pathlib import Path


class Config:
    """Application configuration loaded from environment variables."""

    BASE_DIR = Path(__file__).resolve().parent

    # Production must provide a real SECRET_KEY through the environment.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "tasks.db"))
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = int(os.environ.get("SESSION_LIFETIME_SECONDS", 8 * 60 * 60))

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", MAIL_USERNAME)

    COMPANY_NAME = os.environ.get("COMPANY_NAME", "")
    COMPANY_NAME_EN = os.environ.get("COMPANY_NAME_EN", "")
    COMPANY_PHONE = os.environ.get("COMPANY_PHONE", "")
    COMPANY_ADDRESS = os.environ.get("COMPANY_ADDRESS", "")
    COMPANY_LOGO = os.environ.get("COMPANY_LOGO", "logo.png")

    # Legacy default credentials are no longer defined in source configuration.
    DEFAULT_USERNAME = os.environ.get("DEFAULT_USERNAME", "")
    DEFAULT_PASSWORD = os.environ.get("DEFAULT_PASSWORD", "")
