# utils/decorators.py
from functools import wraps
from flask import session, flash, redirect, url_for
from models import has_permission, get_user_permissions

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('⛔ يرجى تسجيل الدخول أولاً', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session:
                flash('⛔ غير مصرح لك', 'danger')
                return redirect(url_for('auth.login'))
            if session['user_role'] not in allowed_roles:
                flash('⛔ ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def permission_required(permission_name):
    """Decorator للتحقق من الصلاحية"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('⛔ يرجى تسجيل الدخول أولاً', 'warning')
                return redirect(url_for('auth.login'))
            
            if has_permission(session['user_id'], permission_name):
                return f(*args, **kwargs)
            else:
                flash(f'⛔ ليس لديك صلاحية: {permission_name}', 'danger')
                return redirect(url_for('index'))
        return decorated_function
    return decorator

def permissions_required(permission_names):
    """Decorator للتحقق من عدة صلاحيات (يحتاج واحدة على الأقل)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('⛔ يرجى تسجيل الدخول أولاً', 'warning')
                return redirect(url_for('auth.login'))
            
            user_perms = get_user_permissions(session['user_id'])
            if any(perm in user_perms for perm in permission_names):
                return f(*args, **kwargs)
            else:
                flash('⛔ ليس لديك الصلاحية المناسبة', 'danger')
                return redirect(url_for('index'))
        return decorated_function
    return decorator