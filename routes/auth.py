from flask import render_template, request, redirect, url_for, session, flash
import hashlib
import hmac
import bcrypt
from models import get_db, hash_password
from routes import auth_bp
from utils import get_company_settings, log_activity


MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


def _client_ip():
    return request.remote_addr or ''


def _is_legacy_sha256(stored_password):
    return (
        bool(stored_password)
        and len(stored_password) == 64
        and all(c in '0123456789abcdef' for c in stored_password.lower())
    )


def _verify_password(password, stored_password):
    """Verify bcrypt hashes and transparently accept legacy SHA-256 hashes."""
    if not stored_password:
        return False
    if stored_password.startswith('$2'):
        try:
            return bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8'))
        except (ValueError, TypeError):
            return False
    if _is_legacy_sha256(stored_password):
        candidate = hashlib.sha256(password.encode('utf-8')).hexdigest()
        return hmac.compare_digest(candidate, stored_password)
    return False


def _is_login_locked(conn, username, ip_address):
    row = conn.execute(
        '''
        SELECT COUNT(*) AS failures
        FROM login_attempts
        WHERE username = ?
          AND ip_address = ?
          AND success = 0
          AND attempt_time >= datetime('now', ?)
        ''',
        (username, ip_address, f'-{LOCKOUT_MINUTES} minutes')
    ).fetchone()
    return row['failures'] >= MAX_FAILED_LOGINS


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
        if _is_login_locked(conn, username, ip_address):
            conn.close()
            flash('⛔ تم إيقاف محاولات تسجيل الدخول مؤقتاً. حاول مرة أخرى لاحقاً.', 'danger')
            return render_template('login.html', settings=get_company_settings())

        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND is_active = 1',
            (username,)
        ).fetchone()
        success = bool(user and _verify_password(password, user['password']))

        conn.execute(
            'INSERT INTO login_attempts (username, ip_address, success) VALUES (?, ?, ?)',
            (username, ip_address, 1 if success else 0)
        )

        if success:
            # Migrate legacy SHA-256 hashes to bcrypt after a valid login.
            if _is_legacy_sha256(user['password']):
                conn.execute(
                    'UPDATE users SET password = ? WHERE id = ?',
                    (hash_password(password), user['id'])
                )
            conn.commit()
            conn.close()

            # Rotate session contents after authentication to reduce session fixation risk.
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
            elif user['role'] == 'موظف':
                return redirect(url_for('tasks.tasks'))
            return redirect(url_for('clients.clients'))

        conn.commit()
        conn.close()
        flash('❌ اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')

    settings = get_company_settings()
    return render_template('login.html', settings=settings)


@auth_bp.route('/logout')
def logout():
    try:
        user_id = session.get('user_id')
        if user_id:
            log_activity(user_id, 'تسجيل خروج', '')
        session.clear()
        flash('✅ تم تسجيل الخروج بنجاح', 'success')
    except Exception:
        session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in ['ar', 'en']:
        session['lang'] = lang
        flash(f'✅ تم تغيير اللغة إلى {lang}', 'success')
    return redirect(request.referrer or url_for('index'))
