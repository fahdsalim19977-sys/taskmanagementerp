# utils/__init__.py
"""
الحزمة المساعدة (Utilities) للتطبيق
"""

# استيراد الدوال من utils.py (الموجود داخل نفس المجلد)
from .utils import (
    log_activity,
    check_role,
    get_company_settings,
    get_trainers,
    get_lang,
    t
)

# استيراد الديكورات من decorators.py
from .decorators import login_required, role_required, permission_required