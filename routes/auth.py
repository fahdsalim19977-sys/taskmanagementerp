# routes/auth.py
from flask import render_template, request, redirect, url_for, session, flash
from models import get_db, hash_password, verify_password
from routes import auth_bp
from utils import get_company_settings, log_activity

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
                return redirect(url_for('tasks_bp.tasks'))
            else:
                return redirect(url_for('clients_bp.clients'))
        else:
            flash('❌ اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    
    settings = get_company_settings()
    return render_template('login.html', settings=settings)