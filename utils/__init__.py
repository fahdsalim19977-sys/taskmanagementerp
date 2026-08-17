# utils/__init__.py
"""
الحزمة المساعدة (Utilities) للتطبيق
تحتوي على دوال مساعدة وأدوات مشتركة
"""

from .decorators import login_required, role_required, permission_required
from .helpers import get_company_settings, get_trainers, get_lang, t, log_activity, check_role

# هذا الملف يجعل مجلد utils Package معترف به في Python