# routes/auth.py
from flask import render_template, request, redirect, url_for, session, flash
from models import get_db, verify_password, hash_password, is_legacy_password_hash
from routes import auth_bp
from utils import get_company_settings, log_activity


def _client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()


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
        user = conn.execute('SELECT * FROM users WHERE username = ? AND is_active = 1', (username,)).fetchone()
        success = bool(user and verify_password(user['password'], password))
        conn.execute(
            'INSERT INTO login_attempts (username, ip_address, success) VALUES (?, ?, ?)',
            (username, ip_address, 1 if success else 0)
        )

        if success:
            # Transparent migration of legacy SHA-256 hashes after a valid login.
            if is_legacy_password_hash(user['password']):
                conn.execute('UPDATE users SET password = ? WHERE id = ?', (hash_password(password), user['id']))
            conn.commit()
            conn.close()

            session.clear()
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            session['username'] = user['username']
            session.permanent = True

            flash(f'مرحباً {user["name"]}! 👋', 'success')
            if user['role'] == 'مدير':
                return redirect(url_for('index'))
            elif user['role'] == 'موظف':
                return redirect(url_for('tasks_bp.tasks'))
            return redirect(url_for('clients_bp.clients'))

        conn.commit()
        conn.close()
        flash('❌ اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')

    settings = get_company_settings()
    return render_template('login.html', settings=settings)


@auth_bp.route('/logout', methods=['POST'])
def logout():
    try:
        user_id = session.get('user_id')
        if user_id:
            log_activity(user_id, 'تسجيل خروج', '')
        session.clear()
        flash('✅ تم تسجيل الخروج بنجاح', 'success')
    except Exception as e:
        print(f'Error in logout: {str(e)}')
        session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in ['ar', 'en']:
        session['lang'] = lang
        flash(f'✅ تم تغيير اللغة إلى {lang}', 'success')
    return redirect(request.referrer or url_for('index'))
