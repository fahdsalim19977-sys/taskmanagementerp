# utils/decorators.py
from functools import wraps
from flask import session, flash, redirect, url_for

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

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # يمكنك إضافة منطق التحقق من الصلاحية هنا
            conn = get_db()
            user = conn.execute('SELECT * FROM users WHERE id = ?', (session.get('user_id'),)).fetchone()
            conn.close()
            if not user:
                flash('⛔ غير مصرح لك', 'danger')
                return redirect(url_for('index'))
            # هنا يمكنك إضافة منطق التحقق من الصلاحية بناءً على الدور
            return f(*args, **kwargs)
        return decorated_function
    return decorator