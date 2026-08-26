from flask import flash, redirect, render_template, request, session, url_for

from models import get_db
from routes import auth_bp
from utils import get_company_settings, log_activity
from utils.security import hash_password, is_legacy_password_hash, verify_password

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _too_many_failed_attempts(conn, username, ip_address):
    row = conn.execute(
        """
        SELECT COUNT(*) AS failures
        FROM login_attempts
        WHERE username = ? AND ip_address = ? AND success = 0
          AND attempt_time >= datetime('now', ?)
        """,
        (username, ip_address, f"-{LOCKOUT_MINUTES} minutes"),
    ).fetchone()
    return row["failures"] >= MAX_FAILED_ATTEMPTS


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        ip_address = _client_ip()

        if not username or not password:
            flash('❌ يرجى إدخال اسم المستخدم وكلمة المرور', 'danger')
            return render_template('login.html', settings=get_company_settings())

        conn = get_db()
        if _too_many_failed_attempts(conn, username, ip_address):
            conn.close()
            flash('⛔ تم إيقاف محاولات تسجيل الدخول مؤقتاً. حاول مرة أخرى بعد 15 دقيقة.', 'danger')
            return render_template('login.html', settings=get_company_settings())

        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND is_active = 1',
            (username,),
        ).fetchone()
        success = bool(user and verify_password(user['password'], password))

        conn.execute(
            'INSERT INTO login_attempts (username, ip_address, success) VALUES (?, ?, ?)',
            (username, ip_address, 1 if success else 0),
        )

        if success:
            if is_legacy_password_hash(user['password']):
                conn.execute(
                    'UPDATE users SET password = ? WHERE id = ?',
                    (hash_password(password), user['id']),
                )
            conn.commit()
            conn.close()

            session.clear()
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            session['username'] = user['username']
            session.permanent = True

            flash(f'مرحباً {user["name"]}! 👋', 'success')
            log_activity(session['user_id'], 'تسجيل دخول', '')

            if user['role'] == 'مدير':
                return redirect(url_for('index'))
            if user['role'] == 'موظف':
                return redirect(url_for('tasks_bp.tasks'))
            return redirect(url_for('clients_bp.clients'))

        conn.commit()
        conn.close()
        flash('❌ اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')

    return render_template('login.html', settings=get_company_settings())


@auth_bp.route('/logout', methods=['POST'])
def logout():
    try:
        user_id = session.get('user_id')
        if user_id:
            log_activity(user_id, 'تسجيل خروج', '')
        session.clear()
        flash('✅ تم تسجيل الخروج بنجاح', 'success')
    except Exception as exc:
        print(f'Error in logout: {exc}')
        session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in ['ar', 'en']:
        session['lang'] = lang
        flash(f'✅ تم تغيير اللغة إلى {lang}', 'success')
    return redirect(request.referrer or url_for('index'))
