# routes/auth.py
from flask import render_template, request, redirect, url_for, session, flash
from models import get_db, hash_password
from routes import auth_bp
from utils import get_company_settings, log_activity
from models import verify_password

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        conn = get_db()
        user = conn.execute('''
            SELECT * FROM users WHERE username = ? AND is_active = 1
        ''', (username,)).fetchone()
        conn.close()
        
        if user and verify_password(password, user['password']):
            # تسجيل الدخول ناجح
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            # ...
        else:
            flash('❌ اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    
    settings = get_company_settings()
    return render_template('login.html', settings=settings)

@auth_bp.route('/logout')
def logout():
    try:
        if 'user_id' in session:
            log_activity(session['user_id'], 'تسجيل خروج', '')
        session.clear()
        flash('✅ تم تسجيل الخروج بنجاح', 'success')
        return redirect(url_for('auth.login'))
    except Exception as e:
        print(f"Error in logout: {str(e)}")
        session.clear()
        return redirect(url_for('auth.login'))

@auth_bp.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in ['ar', 'en']:
        session['lang'] = lang
        flash(f'✅ تم تغيير اللغة إلى {lang}', 'success')
    return redirect(request.referrer or url_for('index'))