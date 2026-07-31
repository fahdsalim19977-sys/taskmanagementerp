# app.py
import os
import sys
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from models import get_db, init_db, hash_password
from config import Config
from translations import get_text
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import pandas as pd
import json
import sqlite3

# ===== إعدادات IIS =====
if os.name == 'nt':
    sys.path.insert(0, os.path.dirname(__file__))
    

# ============================================================
# إنشاء التطبيق
# ============================================================
app = Flask(__name__)
app.config.from_object(Config)

# التأكد من وجود مجلدات
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)

# ============================================================
# دوال اللغة
# ============================================================
def get_lang():
    return session.get('lang', 'ar')

def t(key):
    return get_text(key, get_lang())

# ============================================================
# دوال مساعدة
# ============================================================
def send_email(to_email, subject, body, attachment=None):
    try:
        msg = MIMEMultipart()
        msg['From'] = app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        if attachment:
            with open(attachment, 'rb') as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(attachment))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment)}"'
                msg.attach(part)
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

def log_activity(user_id, action, details=None):
    conn = get_db()
    conn.execute('INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)', 
                 (user_id, action, details))
    conn.commit()
    conn.close()

def check_role(allowed_roles):
    if 'user_id' not in session:
        return False
    conn = get_db()
    user = conn.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return user and user['role'] in allowed_roles

def get_company_settings():
    conn = get_db()
    settings = conn.execute('SELECT * FROM company_settings LIMIT 1').fetchone()
    conn.close()
    return settings

def get_trainers():
    """جلب قائمة المدربين النشطين"""
    conn = get_db()
    trainers = conn.execute('''
        SELECT id, name FROM trainers 
        WHERE is_active = 1
        ORDER BY name
    ''').fetchall()
    conn.close()
    return trainers

# ============================================================
# تبديل اللغة
# ============================================================
@app.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in ['ar', 'en']:
        session['lang'] = lang
        flash(f'✅ تم تغيير اللغة إلى {lang}', 'success')
    return redirect(request.referrer or url_for('index'))

@app.context_processor
def utility_processor():
    settings = get_company_settings()
    return {
        't': t,
        'get_lang': get_lang,
        'datetime': datetime,
        'settings': settings
    }

# ============================================================
# تهيئة قاعدة البيانات
# ============================================================
init_db()

# ============================================================
# الصفحة الرئيسية
# ============================================================
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    total_tasks = conn.execute('SELECT COUNT(*) as count FROM tasks').fetchone()['count']
    completed_tasks = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "مكتملة"').fetchone()['count']
    overdue_tasks = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE due_date < date("now") AND status != "مكتملة"').fetchone()['count']
    in_progress = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "قيد التنفيذ"').fetchone()['count']
    total_clients = conn.execute('SELECT COUNT(*) as count FROM clients').fetchone()['count']
    total_users = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
    upcoming_meetings = conn.execute('SELECT COUNT(*) as count FROM meetings WHERE date(meeting_date) >= date("now") AND status = "مجدول"').fetchone()['count']
    total_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع"').fetchone()['total'] or 0
    
    overdue_list = conn.execute('''
        SELECT tasks.*, clients.name as client_name, users.name as assigned_name 
        FROM tasks 
        JOIN clients ON tasks.client_id = clients.id 
        JOIN users ON tasks.assigned_to = users.id 
        WHERE due_date < date("now") AND status != "مكتملة"
        ORDER BY due_date ASC
        LIMIT 10
    ''').fetchall()
    
    recent_activity = conn.execute('''
        SELECT activity_log.*, users.name as user_name 
        FROM activity_log 
        JOIN users ON activity_log.user_id = users.id 
        ORDER BY activity_log.created_at DESC 
        LIMIT 10
    ''').fetchall()
    conn.close()
    settings = get_company_settings()
    
    return render_template('index.html', 
                         total_tasks=total_tasks,
                         completed_tasks=completed_tasks,
                         overdue_tasks=overdue_tasks,
                         in_progress=in_progress,
                         total_clients=total_clients,
                         total_users=total_users,
                         upcoming_meetings=upcoming_meetings,
                         total_revenue=total_revenue,
                         overdue_list=overdue_list,
                         recent_activity=recent_activity,
                         settings=settings)

# ============================================================
# تسجيل الدخول والخروج
# ============================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        conn = get_db()
        user = conn.execute('''
            SELECT * FROM users 
            WHERE username = ? AND password = ? AND is_active = 1
        ''', (username, hash_password(password))).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            session['username'] = user['username']
            session.permanent = True
            
            flash(f'مرحباً {user["name"]}! 👋', 'success')
            
            if user['role'] == 'مدير':
                return redirect(url_for('index'))
            elif user['role'] == 'موظف':
                return redirect(url_for('tasks'))
            else:
                return redirect(url_for('clients'))
        else:
            flash('❌ اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    
    settings = get_company_settings()
    return render_template('login.html', settings=settings)

@app.route('/logout')
def logout():
    """تسجيل الخروج"""
    try:
        if 'user_id' in session:
            log_activity(session['user_id'], 'تسجيل خروج', '')
        
        session.clear()
        resp = redirect(url_for('login'))
        resp.set_cookie('session', '', expires=0)
        
        flash('✅ تم تسجيل الخروج بنجاح', 'success')
        return resp
    except Exception as e:
        print(f"Error in logout: {str(e)}")
        session.clear()
        return redirect(url_for('login'))

# ============================================================
# إدارة المستخدمين
# ============================================================
@app.route('/users')
def users():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    conn = get_db()
    users_list = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('users.html', users=users_list)

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        conn = get_db()
        try:
            conn.execute('INSERT INTO users (username, name, email, password, role) VALUES (?, ?, ?, ?, ?)', 
                        (username, name, email, hash_password(password), role))
            conn.commit()
            flash('✅ تم إضافة المستخدم بنجاح', 'success')
            log_activity(session['user_id'], 'إضافة مستخدم', f'أضاف {username}')
        except sqlite3.IntegrityError:
            flash('❌ اسم المستخدم أو البريد موجود مسبقاً', 'danger')
        conn.close()
        return redirect(url_for('users'))
    return render_template('add_user.html')

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['user_role'] != 'مدير':
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('users'))
    if user_id == session['user_id']:
        flash('❌ لا يمكنك حذف حسابك الخاص', 'danger')
        return redirect(url_for('users'))
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('❌ المستخدم غير موجود', 'danger')
        conn.close()
        return redirect(url_for('users'))
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('✅ تم حذف المستخدم بنجاح', 'success')
    log_activity(session['user_id'], 'حذف مستخدم', f'حذف {user["username"]}')
    return redirect(url_for('users'))

# ============================================================
# إدارة العملاء
# ============================================================
@app.route('/clients')
def clients():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    clients_list = conn.execute('''
        SELECT clients.*, 
               GROUP_CONCAT(trainers.name, ', ') as trainer_names
        FROM clients
        LEFT JOIN client_trainers ON clients.id = client_trainers.client_id
        LEFT JOIN trainers ON client_trainers.trainer_id = trainers.id
        GROUP BY clients.id
        ORDER BY clients.name
    ''').fetchall()
    conn.close()
    return render_template('clients.html', clients=clients_list)

@app.route('/add_client', methods=['GET', 'POST'])
def add_client():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    trainers = get_trainers()
    
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form.get('phone', '')
        email = request.form.get('email', '')
        address = request.form.get('address', '')
        company_name = request.form.get('company_name', '')
        notes = request.form.get('notes', '')
        trainer_ids = request.form.getlist('trainer_ids')
        
        conn = get_db()
        
        cursor = conn.execute('''
            INSERT INTO clients (name, phone, email, address, company_name, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, phone, email, address, company_name, notes))
        client_id = cursor.lastrowid
        
        for trainer_id in trainer_ids:
            if trainer_id:
                conn.execute('''
                    INSERT INTO client_trainers (client_id, trainer_id)
                    VALUES (?, ?)
                ''', (client_id, trainer_id))
        
        conn.commit()
        conn.close()
        
        flash('✅ تم إضافة العميل بنجاح', 'success')
        log_activity(session['user_id'], 'إضافة عميل', f'أضاف {name}')
        return redirect(url_for('clients'))
    
    return render_template('add_client.html', trainers=trainers)

@app.route('/edit_client/<int:client_id>', methods=['GET', 'POST'])
def edit_client(client_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    
    if not client:
        flash('❌ العميل غير موجود', 'danger')
        conn.close()
        return redirect(url_for('clients'))
    
    current_trainers = conn.execute('''
        SELECT trainer_id FROM client_trainers WHERE client_id = ?
    ''', (client_id,)).fetchall()
    current_trainer_ids = [t['trainer_id'] for t in current_trainers]
    
    trainers = get_trainers()
    
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form.get('phone', '')
        email = request.form.get('email', '')
        address = request.form.get('address', '')
        company_name = request.form.get('company_name', '')
        notes = request.form.get('notes', '')
        trainer_ids = request.form.getlist('trainer_ids')
        
        conn.execute('''
            UPDATE clients SET 
                name = ?, phone = ?, email = ?, address = ?, 
                company_name = ?, notes = ?
            WHERE id = ?
        ''', (name, phone, email, address, company_name, notes, client_id))
        
        conn.execute('DELETE FROM client_trainers WHERE client_id = ?', (client_id,))
        for trainer_id in trainer_ids:
            if trainer_id:
                conn.execute('''
                    INSERT INTO client_trainers (client_id, trainer_id)
                    VALUES (?, ?)
                ''', (client_id, trainer_id))
        
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث العميل بنجاح', 'success')
        log_activity(session['user_id'], 'تحديث عميل', f'حدث {name}')
        return redirect(url_for('clients'))
    
    conn.close()
    return render_template('edit_client.html', 
                         client=client, 
                         trainers=trainers, 
                         current_trainer_ids=current_trainer_ids)

@app.route('/delete_client/<int:client_id>', methods=['POST'])
def delete_client(client_id):
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('clients'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('❌ العميل غير موجود', 'danger')
        conn.close()
        return redirect(url_for('clients'))
    
    conn.execute('DELETE FROM clients WHERE id = ?', (client_id,))
    conn.execute('DELETE FROM client_trainers WHERE client_id = ?', (client_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف العميل بنجاح', 'success')
    log_activity(session['user_id'], 'حذف عميل', f'حذف عميل رقم {client_id}')
    return redirect(url_for('clients'))

# ============================================================
# إدارة المهام (التدريبات)
# ============================================================
@app.route('/tasks')
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    user_role = session['user_role']
    if user_role == 'موظف':
        task_list = conn.execute('''
            SELECT tasks.*, clients.name as client_name, clients.company_name, users.name as assigned_name 
            FROM tasks 
            JOIN clients ON tasks.client_id = clients.id 
            JOIN users ON tasks.assigned_to = users.id 
            WHERE tasks.assigned_to = ?
            ORDER BY tasks.due_date ASC
        ''', (session['user_id'],)).fetchall()
    else:
        task_list = conn.execute('''
            SELECT tasks.*, clients.name as client_name, clients.company_name, users.name as assigned_name 
            FROM tasks 
            JOIN clients ON tasks.client_id = clients.id 
            JOIN users ON tasks.assigned_to = users.id 
            ORDER BY tasks.due_date ASC
        ''').fetchall()
    conn.close()
    return render_template('tasks.html', tasks=task_list, today=datetime.now().date())

@app.route('/add_task', methods=['GET', 'POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['user_role'] == 'مراقب':
        flash('⛔ ليس لديك صلاحية لإضافة مهام', 'danger')
        return redirect(url_for('tasks'))
    
    conn = get_db()
    clients = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
    users = conn.execute('SELECT * FROM users WHERE role != "مراقب" ORDER BY name').fetchall()
    meetings = conn.execute('SELECT id, title, client_id FROM meetings WHERE date(meeting_date) >= date("now") AND status = "مجدول" ORDER BY meeting_date ASC').fetchall()
    conn.close()
    
    if request.method == 'POST':
        client_id = request.form['client_id']
        assigned_to = request.form['assigned_to']
        title = request.form['title']
        description = request.form.get('description', '')
        due_date = request.form['due_date']
        priority = request.form['priority']
        estimated_duration = request.form.get('estimated_duration', 0)
        meeting_id = request.form.get('meeting_id') or None
        task_group = request.form.get('task_group', '')
        
        conn = get_db()
        cursor = conn.execute('''
            INSERT INTO tasks (client_id, assigned_to, title, description, due_date, priority, 
                             estimated_duration, meeting_id, task_group)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, assigned_to, title, description, due_date, priority, 
              estimated_duration, meeting_id, task_group))
        task_id = cursor.lastrowid
        conn.commit()
        
        message = f'📋 تم تكليفك بمهمة جديدة: {title}'
        conn.execute('INSERT INTO notifications (user_id, task_id, message) VALUES (?, ?, ?)', 
                    (assigned_to, task_id, message))
        conn.commit()
        conn.close()
        
        flash('✅ تم إضافة المهمة بنجاح', 'success')
        log_activity(session['user_id'], 'إضافة مهمة', f'أضاف {title}')
        return redirect(url_for('tasks'))
    
    return render_template('add_task.html', clients=clients, users=users, meetings=meetings)

@app.route('/task/<int:task_id>')
def task_details(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    task = conn.execute('''
        SELECT tasks.*, 
               clients.name as client_name, 
               clients.phone as client_phone,
               clients.email as client_email,
               clients.address as client_address,
               clients.company_name as client_company,
               users.name as assigned_name,
               users.email as assigned_email
        FROM tasks 
        JOIN clients ON tasks.client_id = clients.id 
        JOIN users ON tasks.assigned_to = users.id 
        WHERE tasks.id = ?
    ''', (task_id,)).fetchone()
    
    if not task:
        flash('❌ المهمة غير موجودة', 'danger')
        conn.close()
        return redirect(url_for('tasks'))
    
    updates = conn.execute('''
        SELECT task_updates.*, users.name as user_name
        FROM task_updates
        JOIN users ON task_updates.user_id = users.id
        WHERE task_updates.task_id = ?
        ORDER BY task_updates.created_at DESC
    ''', (task_id,)).fetchall()
    conn.close()
    return render_template('task_details.html', task=task, updates=updates, today=datetime.now().date())

@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    task = conn.execute('SELECT tasks.*, clients.name as client_name FROM tasks JOIN clients ON tasks.client_id = clients.id WHERE tasks.id = ?', (task_id,)).fetchone()
    
    if not task:
        flash('❌ المهمة غير موجودة', 'danger')
        conn.close()
        return redirect(url_for('tasks'))
    
    user_role = session['user_role']
    if user_role == 'مراقب':
        flash('⛔ ليس لديك صلاحية لتعديل المهام', 'danger')
        conn.close()
        return redirect(url_for('tasks'))
    
    if user_role == 'موظف' and task['assigned_to'] != session['user_id']:
        flash('⛔ يمكنك تعديل مهامك فقط', 'danger')
        conn.close()
        return redirect(url_for('tasks'))
    
    clients = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
    users = conn.execute('SELECT * FROM users WHERE role != "مراقب" ORDER BY name').fetchall()
    
    if request.method == 'POST':
        client_id = request.form['client_id']
        assigned_to = request.form['assigned_to']
        title = request.form['title']
        description = request.form.get('description', '')
        due_date = request.form['due_date']
        priority = request.form['priority']
        estimated_duration = request.form.get('estimated_duration', 0)
        task_group = request.form.get('task_group', '')
        
        conn.execute('''
            UPDATE tasks SET 
                client_id = ?,
                assigned_to = ?,
                title = ?,
                description = ?,
                due_date = ?,
                priority = ?,
                estimated_duration = ?,
                task_group = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (client_id, assigned_to, title, description, due_date, priority, 
              estimated_duration, task_group, task_id))
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث المهمة بنجاح', 'success')
        log_activity(session['user_id'], 'تعديل مهمة', f'عدل {title}')
        return redirect(url_for('tasks'))
    
    conn.close()
    return render_template('edit_task.html', task=task, clients=clients, users=users)

@app.route('/update_task_status/<int:task_id>', methods=['POST'])
def update_task_status(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    status = request.form['status']
    completion = request.form.get('completion_percentage', 0)
    actual_duration = request.form.get('actual_duration', 0)
    
    conn = get_db()
    conn.execute('UPDATE tasks SET status = ?, completion_percentage = ?, actual_duration = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', 
                (status, completion, actual_duration, task_id))
    conn.commit()
    conn.close()
    
    flash('✅ تم تحديث حالة المهمة', 'success')
    log_activity(session['user_id'], 'تحديث مهمة', f'غير حالة المهمة {task_id}')
    return redirect(url_for('tasks'))

@app.route('/add_note/<int:task_id>', methods=['POST'])
def add_note(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    note = request.form['note']
    file = request.files.get('attachment')
    attachment_path = None
    if file and file.filename:
        filename = secure_filename(file.filename)
        name_parts = filename.rsplit('.', 1)
        if len(name_parts) > 1:
            filename = f"{name_parts[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{name_parts[1]}"
        else:
            filename = f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        attachment_path = file_path
    
    conn = get_db()
    conn.execute('INSERT INTO task_updates (task_id, user_id, note, attachment_path) VALUES (?, ?, ?, ?)', 
                (task_id, session['user_id'], note, attachment_path))
    conn.commit()
    conn.close()
    
    flash('📝 تم إضافة الملاحظة بنجاح', 'success')
    log_activity(session['user_id'], 'إضافة ملاحظة', f'أضاف ملاحظة للمهمة {task_id}')
    return redirect(url_for('tasks'))

@app.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        flash('❌ المهمة غير موجودة', 'danger')
        conn.close()
        return redirect(url_for('tasks'))
    
    user_role = session['user_role']
    if user_role == 'مراقب':
        flash('⛔ ليس لديك صلاحية لحذف المهام', 'danger')
        conn.close()
        return redirect(url_for('tasks'))
    if user_role == 'موظف' and task['assigned_to'] != session['user_id']:
        flash('⛔ يمكنك حذف مهامك فقط', 'danger')
        conn.close()
        return redirect(url_for('tasks'))
    
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف المهمة بنجاح', 'success')
    log_activity(session['user_id'], 'حذف مهمة', f'حذف مهمة رقم {task_id}')
    return redirect(url_for('tasks'))

@app.route('/tasks/search')
def search_tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    search_term = request.args.get('q', '').strip()
    conn = get_db()
    user_role = session['user_role']
    
    if user_role == 'موظف':
        query = '''
            SELECT tasks.*, clients.name as client_name, clients.company_name, users.name as assigned_name 
            FROM tasks 
            JOIN clients ON tasks.client_id = clients.id 
            JOIN users ON tasks.assigned_to = users.id 
            WHERE tasks.assigned_to = ? AND clients.name LIKE ?
            ORDER BY tasks.due_date ASC
        '''
        params = (session['user_id'], f'%{search_term}%')
    else:
        query = '''
            SELECT tasks.*, clients.name as client_name, clients.company_name, users.name as assigned_name 
            FROM tasks 
            JOIN clients ON tasks.client_id = clients.id 
            JOIN users ON tasks.assigned_to = users.id 
            WHERE clients.name LIKE ?
            ORDER BY tasks.due_date ASC
        '''
        params = (f'%{search_term}%',)
    
    task_list = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('tasks.html', tasks=task_list, today=datetime.now().date(), search_term=search_term)

@app.route('/group_tasks', methods=['POST'])
def group_tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    client_id = request.form['client_id']
    group_name = request.form['group_name']
    conn = get_db()
    conn.execute('UPDATE tasks SET task_group = ? WHERE client_id = ? AND task_group IS NULL', 
                (group_name, client_id))
    conn.commit()
    conn.close()
    
    flash(f'✅ تم تجميع مهام العميل تحت مجموعة "{group_name}"', 'success')
    return redirect(url_for('client_tasks', client_id=client_id))

# ============================================================
# إدارة المدربين
# ============================================================
@app.route('/trainers')
def trainers():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    trainers_list = conn.execute('''
        SELECT trainers.*, 
               COUNT(client_trainers.client_id) as client_count
        FROM trainers
        LEFT JOIN client_trainers ON trainers.id = client_trainers.trainer_id
        GROUP BY trainers.id
        ORDER BY trainers.name
    ''').fetchall()
    conn.close()
    return render_template('trainers.html', trainers=trainers_list)

@app.route('/add_trainer', methods=['GET', 'POST'])
def add_trainer():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form.get('phone', '')
        email = request.form.get('email', '')
        specialty = request.form.get('specialty', '')
        notes = request.form.get('notes', '')
        
        conn = get_db()
        conn.execute('''
            INSERT INTO trainers (name, phone, email, specialty, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, phone, email, specialty, notes))
        conn.commit()
        conn.close()
        
        flash('✅ تم إضافة المدرب بنجاح', 'success')
        log_activity(session['user_id'], 'إضافة مدرب', f'أضاف {name}')
        return redirect(url_for('trainers'))
    
    return render_template('add_trainer.html')

@app.route('/edit_trainer/<int:trainer_id>', methods=['GET', 'POST'])
def edit_trainer(trainer_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    trainer = conn.execute('SELECT * FROM trainers WHERE id = ?', (trainer_id,)).fetchone()
    
    if not trainer:
        flash('❌ المدرب غير موجود', 'danger')
        conn.close()
        return redirect(url_for('trainers'))
    
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form.get('phone', '')
        email = request.form.get('email', '')
        specialty = request.form.get('specialty', '')
        notes = request.form.get('notes', '')
        is_active = request.form.get('is_active', '1')
        
        conn.execute('''
            UPDATE trainers SET 
                name = ?, phone = ?, email = ?, specialty = ?, 
                notes = ?, is_active = ?
            WHERE id = ?
        ''', (name, phone, email, specialty, notes, is_active, trainer_id))
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث المدرب بنجاح', 'success')
        log_activity(session['user_id'], 'تحديث مدرب', f'حدث {name}')
        return redirect(url_for('trainers'))
    
    conn.close()
    return render_template('edit_trainer.html', trainer=trainer)

@app.route('/delete_trainer/<int:trainer_id>', methods=['POST'])
def delete_trainer(trainer_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    trainer = conn.execute('SELECT * FROM trainers WHERE id = ?', (trainer_id,)).fetchone()
    if not trainer:
        flash('❌ المدرب غير موجود', 'danger')
        conn.close()
        return redirect(url_for('trainers'))
    
    conn.execute('DELETE FROM client_trainers WHERE trainer_id = ?', (trainer_id,))
    conn.execute('DELETE FROM trainers WHERE id = ?', (trainer_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف المدرب بنجاح', 'success')
    log_activity(session['user_id'], 'حذف مدرب', f'حذف {trainer["name"]}')
    return redirect(url_for('trainers'))

# ============================================================
# تقرير شامل للعميل
# ============================================================
@app.route('/print_client_full_report/<int:client_id>')
def print_client_full_report(client_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('❌ العميل غير موجود', 'danger')
        conn.close()
        return redirect(url_for('clients'))
    
    modules = conn.execute('SELECT * FROM client_modules WHERE client_id = ? ORDER BY created_at DESC', (client_id,)).fetchall()
    
    payments = conn.execute('''
        SELECT client_payments.*, 
               client_modules.name as module_name,
               users.name as created_by_name
        FROM client_payments
        LEFT JOIN client_modules ON client_payments.module_id = client_modules.id
        LEFT JOIN users ON client_payments.created_by = users.id
        WHERE client_payments.client_id = ?
        ORDER BY client_payments.created_at DESC
    ''', (client_id,)).fetchall()
    
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total_count,
            SUM(CASE WHEN status = "مدفوع" THEN amount ELSE 0 END) as total_paid,
            SUM(CASE WHEN status = "معلق" THEN amount ELSE 0 END) as total_pending,
            SUM(CASE WHEN status = "متأخر" THEN amount ELSE 0 END) as total_overdue
        FROM client_payments
        WHERE client_id = ?
    ''', (client_id,)).fetchone()
    
    settings = conn.execute('SELECT * FROM company_settings LIMIT 1').fetchone()
    conn.close()
    
    return render_template('print_client_full_report.html',
                         client=client,
                         modules=modules,
                         payments=payments,
                         stats=stats,
                         settings=settings,
                         today=datetime.now().date())

# ============================================================
# مهام العميل
# ============================================================
@app.route('/client_tasks/<int:client_id>')
def client_tasks(client_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    tasks = conn.execute('''
        SELECT tasks.*, users.name as assigned_name
        FROM tasks
        JOIN users ON tasks.assigned_to = users.id
        WHERE tasks.client_id = ?
        ORDER BY tasks.due_date ASC
    ''', (client_id,)).fetchall()
    
    stats = {
        'total': len(tasks),
        'completed': sum(1 for t in tasks if t['status'] == 'مكتملة'),
        'in_progress': sum(1 for t in tasks if t['status'] == 'قيد التنفيذ'),
        'overdue': sum(1 for t in tasks if t['status'] == 'متأخرة'),
        'not_started': sum(1 for t in tasks if t['status'] == 'لم تبدأ'),
    }
    
    avg_duration = conn.execute('SELECT AVG(actual_duration) as avg_duration FROM tasks WHERE client_id = ? AND status = "مكتملة" AND actual_duration > 0', 
                               (client_id,)).fetchone()['avg_duration']
    conn.close()
    return render_template('client_tasks.html', client=client, tasks=tasks, stats=stats, avg_duration=avg_duration, today=datetime.now().date())

@app.route('/print_client_tasks/<int:client_id>')
def print_client_tasks(client_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    tasks = conn.execute('''
        SELECT tasks.*, users.name as assigned_name
        FROM tasks
        JOIN users ON tasks.assigned_to = users.id
        WHERE tasks.client_id = ?
        ORDER BY tasks.due_date ASC
    ''', (client_id,)).fetchall()
    settings = conn.execute('SELECT * FROM company_settings LIMIT 1').fetchone()
    conn.close()
    
    completed_tasks = [t for t in tasks if t['status'] == 'مكتملة']
    in_progress_tasks = [t for t in tasks if t['status'] == 'قيد التنفيذ']
    overdue_tasks = [t for t in tasks if t['status'] == 'متأخرة']
    not_started_tasks = [t for t in tasks if t['status'] == 'لم تبدأ']
    
    return render_template('print_client_tasks.html',
                         client=client,
                         tasks=tasks,
                         completed_tasks=completed_tasks,
                         in_progress_tasks=in_progress_tasks,
                         overdue_tasks=overdue_tasks,
                         not_started_tasks=not_started_tasks,
                         settings=settings,
                         today=datetime.now().date())

# ============================================================
# المواعيد
# ============================================================
@app.route('/meetings')
def meetings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    upcoming = conn.execute('''
        SELECT meetings.*, clients.name as client_name, users.name as created_by_name
        FROM meetings
        JOIN clients ON meetings.client_id = clients.id
        JOIN users ON meetings.created_by = users.id
        WHERE meetings.meeting_date >= datetime("now") AND meetings.status = "مجدول"
        ORDER BY meetings.meeting_date ASC
    ''').fetchall()
    
    past = conn.execute('''
        SELECT meetings.*, clients.name as client_name, users.name as created_by_name
        FROM meetings
        JOIN clients ON meetings.client_id = clients.id
        JOIN users ON meetings.created_by = users.id
        WHERE meetings.meeting_date < datetime("now") OR meetings.status != "مجدول"
        ORDER BY meetings.meeting_date DESC
        LIMIT 20
    ''').fetchall()
    conn.close()
    return render_template('meetings.html', upcoming=upcoming, past=past)

@app.route('/add_meeting', methods=['GET', 'POST'])
def add_meeting():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    clients = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
    conn.close()
    
    if request.method == 'POST':
        client_id = request.form['client_id']
        title = request.form['title']
        description = request.form['description']
        meeting_date = request.form['meeting_date']
        duration = request.form['duration']
        location = request.form['location']
        meeting_link = request.form['meeting_link']
        
        conn = get_db()
        cursor = conn.execute('''
            INSERT INTO meetings (client_id, title, description, meeting_date, duration, location, meeting_link, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, title, description, meeting_date, duration, location, meeting_link, session['user_id']))
        meeting_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        flash('✅ تم إضافة الموعد بنجاح', 'success')
        log_activity(session['user_id'], 'إضافة موعد', f'أضاف موعد: {title}')
        return redirect(url_for('meetings'))
    
    return render_template('add_meeting.html', clients=clients)

@app.route('/meeting/<int:meeting_id>')
def meeting_details(meeting_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    meeting = conn.execute('''
        SELECT meetings.*, clients.name as client_name, clients.phone as client_phone,
               clients.email as client_email, users.name as created_by_name
        FROM meetings
        JOIN clients ON meetings.client_id = clients.id
        JOIN users ON meetings.created_by = users.id
        WHERE meetings.id = ?
    ''', (meeting_id,)).fetchone()
    tasks = conn.execute('SELECT * FROM tasks WHERE meeting_id = ?', (meeting_id,)).fetchall()
    conn.close()
    return render_template('meeting_details.html', meeting=meeting, tasks=tasks)

@app.route('/update_meeting_status/<int:meeting_id>', methods=['POST'])
def update_meeting_status(meeting_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    status = request.form['status']
    conn = get_db()
    conn.execute('UPDATE meetings SET status = ? WHERE id = ?', (status, meeting_id))
    conn.commit()
    conn.close()
    
    flash('✅ تم تحديث حالة الموعد', 'success')
    return redirect(url_for('meetings'))

# ============================================================
# المدفوعات
# ============================================================
@app.route('/all_payments')
def all_payments():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    search_term = request.args.get('q', '').strip()
    conn = get_db()
    
    if search_term:
        payments = conn.execute('''
            SELECT client_payments.*, 
                   clients.name as client_name, 
                   clients.company_name,
                   client_modules.name as module_name,
                   users.name as created_by_name,
                   GROUP_CONCAT(trainers.name, ', ') as trainer_names
            FROM client_payments
            LEFT JOIN clients ON client_payments.client_id = clients.id
            LEFT JOIN client_modules ON client_payments.module_id = client_modules.id
            LEFT JOIN users ON client_payments.created_by = users.id
            LEFT JOIN client_trainers ON clients.id = client_trainers.client_id
            LEFT JOIN trainers ON client_trainers.trainer_id = trainers.id
            WHERE clients.name LIKE ? OR clients.company_name LIKE ?
            GROUP BY client_payments.id
            ORDER BY client_payments.created_at DESC
        ''', (f'%{search_term}%', f'%{search_term}%')).fetchall()
    else:
        payments = conn.execute('''
            SELECT client_payments.*, 
                   clients.name as client_name, 
                   clients.company_name,
                   client_modules.name as module_name,
                   users.name as created_by_name,
                   GROUP_CONCAT(trainers.name, ', ') as trainer_names
            FROM client_payments
            LEFT JOIN clients ON client_payments.client_id = clients.id
            LEFT JOIN client_modules ON client_payments.module_id = client_modules.id
            LEFT JOIN users ON client_payments.created_by = users.id
            LEFT JOIN client_trainers ON clients.id = client_trainers.client_id
            LEFT JOIN trainers ON client_trainers.trainer_id = trainers.id
            GROUP BY client_payments.id
            ORDER BY client_payments.created_at DESC
        ''').fetchall()
    
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total_count,
            SUM(CASE WHEN status = "مدفوع" THEN amount ELSE 0 END) as total_paid,
            SUM(CASE WHEN status = "معلق" THEN amount ELSE 0 END) as total_pending,
            SUM(CASE WHEN status = "متأخر" THEN amount ELSE 0 END) as total_overdue
        FROM client_payments
    ''').fetchone()
    conn.close()
    
    return render_template('all_payments.html', 
                         payments=payments, 
                         stats=stats,
                         search_term=search_term)

@app.route('/add_payment_global', methods=['GET', 'POST'])
def add_payment_global():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    clients = conn.execute('SELECT id, name, company_name FROM clients ORDER BY name').fetchall()
    modules = conn.execute('SELECT id, name FROM client_modules ORDER BY name').fetchall()
    
    if request.method == 'POST':
        client_id = request.form['client_id']
        module_id = request.form.get('module_id') or None
        amount = request.form['amount']
        payment_date = request.form['payment_date']
        due_date = request.form.get('due_date')
        payment_method = request.form['payment_method']
        status = request.form['status']
        invoice_number = request.form.get('invoice_number', '')
        notes = request.form.get('notes', '')
        is_installment = request.form.get('is_installment', '0')
        installment_count = request.form.get('installment_count', 1)
        
        client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
        if not client:
            flash('❌ العميل غير موجود', 'danger')
            conn.close()
            return redirect(url_for('add_payment_global'))
        
        cursor = conn.execute('''
            INSERT INTO client_payments 
            (client_id, module_id, amount, payment_date, due_date, 
             payment_method, status, invoice_number, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, module_id, amount, payment_date, due_date, 
              payment_method, status, invoice_number, notes, session['user_id']))
        payment_id = cursor.lastrowid
        
        if is_installment == '1' and int(installment_count) > 1:
            installment_amount = float(amount) / int(installment_count)
            for i in range(int(installment_count)):
                conn.execute('''
                    INSERT INTO payment_installments 
                    (payment_id, installment_number, amount, due_date)
                    VALUES (?, ?, ?, date(?, "+" || ? || " days"))
                ''', (payment_id, i+1, installment_amount, payment_date, (i+1)*30))
        
        conn.commit()
        conn.close()
        
        flash('✅ تم إضافة الدفعة بنجاح', 'success')
        log_activity(session['user_id'], 'إضافة دفعة', f'أضاف دفعة بقيمة {amount} للعميل {client["name"]}')
        return redirect(url_for('all_payments'))
    
    conn.close()
    return render_template('add_payment_global.html', clients=clients, modules=modules)

@app.route('/edit_payment/<int:payment_id>', methods=['GET', 'POST'])
def edit_payment(payment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    payment = conn.execute('SELECT * FROM client_payments WHERE id = ?', (payment_id,)).fetchone()
    
    if not payment:
        flash('❌ الدفعة غير موجودة', 'danger')
        conn.close()
        return redirect(url_for('all_payments'))
    
    if request.method == 'POST':
        amount = request.form['amount']
        payment_date = request.form['payment_date']
        due_date = request.form.get('due_date')
        payment_method = request.form['payment_method']
        status = request.form['status']
        invoice_number = request.form.get('invoice_number', '')
        notes = request.form.get('notes', '')
        
        conn.execute('''
            UPDATE client_payments SET 
                amount = ?, payment_date = ?, due_date = ?,
                payment_method = ?, status = ?, invoice_number = ?, notes = ?
            WHERE id = ?
        ''', (amount, payment_date, due_date, payment_method, status, 
              invoice_number, notes, payment_id))
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث الدفعة بنجاح', 'success')
        log_activity(session['user_id'], 'تحديث دفعة', f'حدث دفعة {payment_id}')
        return redirect(url_for('all_payments'))
    
    conn.close()
    return render_template('edit_payment.html', payment=payment)

@app.route('/delete_payment/<int:payment_id>', methods=['POST'])
def delete_payment(payment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    payment = conn.execute('SELECT * FROM client_payments WHERE id = ?', (payment_id,)).fetchone()
    if not payment:
        flash('❌ الدفعة غير موجودة', 'danger')
        conn.close()
        return redirect(url_for('all_payments'))
    
    client_id = payment['client_id']
    conn.execute('DELETE FROM client_payments WHERE id = ?', (payment_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف الدفعة بنجاح', 'success')
    log_activity(session['user_id'], 'حذف دفعة', f'حذف دفعة {payment_id}')
    return redirect(url_for('all_payments'))

# ============================================================
# مدفوعات العميل
# ============================================================
@app.route('/client_payments/<int:client_id>')
def client_payments(client_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('❌ العميل غير موجود', 'danger')
        conn.close()
        return redirect(url_for('clients'))
    
    payments = conn.execute('''
        SELECT client_payments.*, 
               client_modules.name as module_name,
               users.name as created_by_name,
               GROUP_CONCAT(trainers.name, ', ') as trainer_names
        FROM client_payments
        LEFT JOIN client_modules ON client_payments.module_id = client_modules.id
        LEFT JOIN users ON client_payments.created_by = users.id
        LEFT JOIN client_trainers ON client_payments.client_id = client_trainers.client_id
        LEFT JOIN trainers ON client_trainers.trainer_id = trainers.id
        WHERE client_payments.client_id = ?
        GROUP BY client_payments.id
        ORDER BY client_payments.created_at DESC
    ''', (client_id,)).fetchall()
    
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total_count,
            SUM(CASE WHEN status = "مدفوع" THEN amount ELSE 0 END) as total_paid,
            SUM(CASE WHEN status = "معلق" THEN amount ELSE 0 END) as total_pending,
            SUM(CASE WHEN status = "متأخر" THEN amount ELSE 0 END) as total_overdue
        FROM client_payments
        WHERE client_id = ?
    ''', (client_id,)).fetchone()
    conn.close()
    
    return render_template('client_payments.html', 
                         client=client, 
                         payments=payments,
                         stats=stats)

# ============================================================
# المديولات
# ============================================================
@app.route('/all_modules')
def all_modules():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    modules = conn.execute('''
        SELECT client_modules.*, 
               clients.name as client_name,
               clients.company_name
        FROM client_modules
        LEFT JOIN clients ON client_modules.client_id = clients.id
        ORDER BY client_modules.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('all_modules.html', modules=modules)

@app.route('/add_module_global', methods=['GET', 'POST'])
def add_module_global():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    clients = conn.execute('SELECT id, name FROM clients ORDER BY name').fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        client_id = request.form.get('client_id') or None
        price = request.form.get('price', 0)
        status = request.form['status']
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        conn.execute('''
            INSERT INTO client_modules (client_id, name, description, price, status, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, name, description, price, status, start_date, end_date))
        conn.commit()
        conn.close()
        
        flash('✅ تم إضافة المديول بنجاح', 'success')
        log_activity(session['user_id'], 'إضافة مديول', f'أضاف {name}')
        return redirect(url_for('all_modules'))
    
    conn.close()
    return render_template('add_module_global.html', clients=clients)

@app.route('/client_modules/<int:client_id>')
def client_modules(client_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('❌ العميل غير موجود', 'danger')
        conn.close()
        return redirect(url_for('clients'))
    
    modules = conn.execute('SELECT * FROM client_modules WHERE client_id = ? ORDER BY created_at DESC', (client_id,)).fetchall()
    conn.close()
    return render_template('client_modules.html', client=client, modules=modules)

@app.route('/add_module/<int:client_id>', methods=['GET', 'POST'])
def add_module(client_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('❌ العميل غير موجود', 'danger')
        conn.close()
        return redirect(url_for('clients'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        price = request.form.get('price', 0)
        status = request.form['status']
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        conn.execute('''
            INSERT INTO client_modules (client_id, name, description, price, status, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, name, description, price, status, start_date, end_date))
        conn.commit()
        conn.close()
        
        flash('✅ تم إضافة المديول بنجاح', 'success')
        log_activity(session['user_id'], 'إضافة مديول', f'أضاف {name} للعميل {client["name"]}')
        return redirect(url_for('client_modules', client_id=client_id))
    
    conn.close()
    return render_template('add_module.html', client=client)

@app.route('/edit_module/<int:module_id>', methods=['GET', 'POST'])
def edit_module(module_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    module = conn.execute('SELECT * FROM client_modules WHERE id = ?', (module_id,)).fetchone()
    if not module:
        flash('❌ المديول غير موجود', 'danger')
        conn.close()
        return redirect(url_for('all_modules'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        price = request.form.get('price', 0)
        status = request.form['status']
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        conn.execute('''
            UPDATE client_modules SET 
                name = ?, description = ?, price = ?, status = ?, 
                start_date = ?, end_date = ?
            WHERE id = ?
        ''', (name, description, price, status, start_date, end_date, module_id))
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث المديول بنجاح', 'success')
        log_activity(session['user_id'], 'تحديث مديول', f'حدث {name}')
        return redirect(url_for('client_modules', client_id=module['client_id']))
    
    conn.close()
    return render_template('edit_module.html', module=module)

@app.route('/delete_module/<int:module_id>', methods=['POST'])
def delete_module(module_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    module = conn.execute('SELECT * FROM client_modules WHERE id = ?', (module_id,)).fetchone()
    if not module:
        flash('❌ المديول غير موجود', 'danger')
        conn.close()
        return redirect(url_for('all_modules'))
    
    client_id = module['client_id']
    conn.execute('DELETE FROM client_modules WHERE id = ?', (module_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف المديول بنجاح', 'success')
    log_activity(session['user_id'], 'حذف مديول', f'حذف {module["name"]}')
    return redirect(url_for('client_modules', client_id=client_id))

# ============================================================
# التقارير
# ============================================================
@app.route('/reports')
def reports():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    total_tasks = conn.execute('SELECT COUNT(*) as count FROM tasks').fetchone()['count']
    completed_count = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "مكتملة"').fetchone()['count']
    in_progress_count = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "قيد التنفيذ"').fetchone()['count']
    overdue_count = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE due_date < date("now") AND status != "مكتملة"').fetchone()['count']
    
    total_payments_count = conn.execute('SELECT COUNT(*) as count FROM client_payments').fetchone()['count']
    total_payments_amount = conn.execute('SELECT SUM(amount) as total FROM client_payments').fetchone()['total'] or 0
    paid_count = conn.execute('SELECT COUNT(*) as count FROM client_payments WHERE status = "مدفوع"').fetchone()['count']
    pending_count = conn.execute('SELECT COUNT(*) as count FROM client_payments WHERE status = "معلق"').fetchone()['count']
    overdue_payments_count = conn.execute('SELECT COUNT(*) as count FROM client_payments WHERE status = "متأخر"').fetchone()['count']
    
    total_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع"').fetchone()['total'] or 0
    monthly_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع" AND payment_date >= date("now", "-30 days")').fetchone()['total'] or 0
    weekly_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع" AND payment_date >= date("now", "-7 days")').fetchone()['total'] or 0
    daily_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع" AND payment_date >= date("now", "-1 day")').fetchone()['total'] or 0
    
    conn.close()
    return render_template('reports.html',
                         total_tasks=total_tasks,
                         completed_count=completed_count,
                         in_progress_count=in_progress_count,
                         overdue_count=overdue_count,
                         total_payments_count=total_payments_count,
                         total_payments_amount=total_payments_amount,
                         paid_count=paid_count,
                         pending_count=pending_count,
                         overdue_payments_count=overdue_payments_count,
                         total_revenue=total_revenue,
                         monthly_revenue=monthly_revenue,
                         weekly_revenue=weekly_revenue,
                         daily_revenue=daily_revenue)

@app.route('/revenue_report')
def revenue_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    total_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع"').fetchone()['total'] or 0
    revenue_by_client = conn.execute('''
        SELECT clients.name, 
               SUM(client_payments.amount) as total,
               COUNT(client_payments.id) as count
        FROM client_payments
        JOIN clients ON client_payments.client_id = clients.id
        WHERE client_payments.status = "مدفوع"
        GROUP BY clients.id
        ORDER BY total DESC
        LIMIT 10
    ''').fetchall()
    revenue_by_month = conn.execute('''
        SELECT strftime("%Y-%m", payment_date) as month,
               SUM(amount) as total
        FROM client_payments
        WHERE status = "مدفوع"
        GROUP BY strftime("%Y-%m", payment_date)
        ORDER BY month DESC
        LIMIT 12
    ''').fetchall()
    conn.close()
    return render_template('revenue_report.html',
                         total_revenue=total_revenue,
                         revenue_by_client=revenue_by_client,
                         revenue_by_month=revenue_by_month)

# ============================================================
# الإشعارات
# ============================================================
@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    notifs = conn.execute('''
        SELECT notifications.*, tasks.title as task_title
        FROM notifications
        LEFT JOIN tasks ON notifications.task_id = tasks.id
        WHERE notifications.user_id = ?
        ORDER BY notifications.created_at DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('notifications.html', notifications=notifs)

@app.route('/mark_notification_read/<int:notif_id>', methods=['POST'])
def mark_notification_read(notif_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    conn.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (notif_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ============================================================
# إعدادات الشركة
# ============================================================
@app.route('/company_settings', methods=['GET', 'POST'])
def company_settings():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db()
    settings = conn.execute('SELECT * FROM company_settings LIMIT 1').fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        name_en = request.form['name_en']
        phone = request.form['phone']
        address = request.form['address']
        email = request.form['email']
        website = request.form['website']
        
        conn.execute('''
            UPDATE company_settings SET 
                name = ?, name_en = ?, phone = ?, address = ?, email = ?, website = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (name, name_en, phone, address, email, website, settings['id']))
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث إعدادات الشركة بنجاح', 'success')
        log_activity(session['user_id'], 'تحديث إعدادات الشركة', '')
        return redirect(url_for('company_settings'))
    
    conn.close()
    return render_template('company_settings.html', settings=settings)

@app.route('/upload_logo', methods=['POST'])
def upload_logo():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('company_settings'))
    
    if 'logo' not in request.files:
        flash('❌ لم يتم اختيار صورة', 'danger')
        return redirect(url_for('company_settings'))
    
    file = request.files['logo']
    if file.filename == '':
        flash('❌ لم يتم اختيار صورة', 'danger')
        return redirect(url_for('company_settings'))
    
    if file:
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'png'
        filename = f"logo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        file_path = os.path.join('static', filename)
        file.save(file_path)
        
        conn = get_db()
        conn.execute('UPDATE company_settings SET logo_path = ?', (filename,))
        conn.commit()
        conn.close()
        
        flash('✅ تم رفع الشعار بنجاح', 'success')
        log_activity(session['user_id'], 'رفع شعار', f'رفع {filename}')
    
    return redirect(url_for('company_settings'))

# ============================================================
# تصدير Excel و PDF
# ============================================================
@app.route('/export_excel')
def export_excel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    tasks = conn.execute('''
        SELECT tasks.id, tasks.title, tasks.description, tasks.status, tasks.priority,
               tasks.due_date, tasks.completion_percentage, tasks.created_at,
               clients.name as client_name, clients.company_name,
               users.name as assigned_name, tasks.estimated_duration, tasks.actual_duration
        FROM tasks 
        JOIN clients ON tasks.client_id = clients.id 
        JOIN users ON tasks.assigned_to = users.id 
        ORDER BY tasks.created_at DESC
    ''').fetchall()
    conn.close()
    
    data = []
    for task in tasks:
        data.append({
            'رقم المهمة': task['id'],
            'العنوان': task['title'],
            'الوصف': task['description'] or '',
            'العميل': task['client_name'],
            'الشركة': task['company_name'] or '',
            'المسؤول': task['assigned_name'],
            'الحالة': task['status'],
            'الأولوية': task['priority'],
            'تاريخ الاستحقاق': task['due_date'],
            'نسبة الإنجاز': f"{task['completion_percentage']}%",
            'المدة المتوقعة': f"{task['estimated_duration'] or 0} ساعة",
            'المدة الفعلية': f"{task['actual_duration'] or 0} ساعة",
            'تاريخ الإنشاء': task['created_at']
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='المهام')
        workbook = writer.book
        worksheet = writer.sheets['المهام']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    return send_file(output, as_attachment=True, 
                    download_name=f'تقرير_المهام_{datetime.now().strftime("%Y%m%d")}.xlsx', 
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/export_pdf')
def export_pdf():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], alignment=1, fontSize=18, textColor=colors.HexColor('#1a237e'))
    subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Normal'], alignment=1, fontSize=10, textColor=colors.grey)
    
    story = []
    story.append(Paragraph("تقرير إنجاز المهام", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
    story.append(Spacer(1, 24))
    
    conn = get_db()
    tasks = conn.execute('''
        SELECT tasks.*, clients.name as client_name, clients.company_name, users.name as assigned_name 
        FROM tasks 
        JOIN clients ON tasks.client_id = clients.id 
        JOIN users ON tasks.assigned_to = users.id 
        ORDER BY tasks.due_date ASC
    ''').fetchall()
    conn.close()
    
    total = len(tasks)
    completed = sum(1 for t in tasks if t['status'] == 'مكتملة')
    overdue = sum(1 for t in tasks if t['status'] == 'متأخرة')
    in_progress = sum(1 for t in tasks if t['status'] == 'قيد التنفيذ')
    
    stats_data = [['الإجمالي', 'مكتملة', 'قيد التنفيذ', 'متأخرة'],
                  [str(total), str(completed), str(in_progress), str(overdue)]]
    stats_table = Table(stats_data, colWidths=[80, 80, 80, 80])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 24))
    
    if tasks:
        data = [['#', 'المهمة', 'العميل', 'المسؤول', 'الحالة', 'الإنجاز', 'التاريخ']]
        for task in tasks:
            data.append([
                str(task['id']),
                task['title'][:30] + '...' if len(task['title']) > 30 else task['title'],
                task['client_name'],
                task['assigned_name'],
                task['status'],
                f"{task['completion_percentage']}%",
                task['due_date']
            ])
        table = Table(data, colWidths=[30, 80, 70, 70, 60, 50, 70])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        story.append(table)
    
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, 
                    download_name=f'report_{datetime.now().strftime("%Y%m%d")}.pdf', 
                    mimetype='application/pdf')

@app.route('/export_full_report')
def export_full_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], alignment=1, fontSize=18, textColor=colors.HexColor('#1a237e'))
    subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Normal'], alignment=1, fontSize=10, textColor=colors.grey)
    heading_style = ParagraphStyle('HeadingStyle', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#1a237e'))
    
    story = []
    story.append(Paragraph("تقرير شامل", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
    story.append(Spacer(1, 24))
    
    conn = get_db()
    
    # ===== 1. تقرير التدريبات =====
    story.append(Paragraph("1. تقرير التدريبات", heading_style))
    story.append(Spacer(1, 12))
    
    total_tasks = conn.execute('SELECT COUNT(*) as count FROM tasks').fetchone()['count']
    completed = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "مكتملة"').fetchone()['count']
    in_progress = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "قيد التنفيذ"').fetchone()['count']
    overdue = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE due_date < date("now") AND status != "مكتملة"').fetchone()['count']
    
    tasks_data = [
        ['الإجمالي', 'مكتملة', 'قيد التنفيذ', 'متأخرة'],
        [str(total_tasks), str(completed), str(in_progress), str(overdue)]
    ]
    tasks_table = Table(tasks_data, colWidths=[100, 100, 100, 100])
    tasks_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(tasks_table)
    story.append(Spacer(1, 24))
    
    # ===== 2. تقرير المدفوعات =====
    story.append(Paragraph("2. تقرير المدفوعات", heading_style))
    story.append(Spacer(1, 12))
    
    total_payments = conn.execute('SELECT COUNT(*) as count FROM client_payments').fetchone()['count']
    total_amount = conn.execute('SELECT SUM(amount) as total FROM client_payments').fetchone()['total'] or 0
    paid = conn.execute('SELECT COUNT(*) as count FROM client_payments WHERE status = "مدفوع"').fetchone()['count']
    pending = conn.execute('SELECT COUNT(*) as count FROM client_payments WHERE status = "معلق"').fetchone()['count']
    overdue_payments = conn.execute('SELECT COUNT(*) as count FROM client_payments WHERE status = "متأخر"').fetchone()['count']
    
    payments_data = [
        ['إجمالي المدفوعات', 'إجمالي المبلغ', 'مدفوع', 'معلق', 'متأخر'],
        [str(total_payments), f"{total_amount} ج.م", str(paid), str(pending), str(overdue_payments)]
    ]
    payments_table = Table(payments_data, colWidths=[80, 80, 80, 80, 80])
    payments_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28a745')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(payments_table)
    story.append(Spacer(1, 24))
    
    # ===== 3. تقرير الإيرادات =====
    story.append(Paragraph("3. تقرير الإيرادات", heading_style))
    story.append(Spacer(1, 12))
    
    total_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع"').fetchone()['total'] or 0
    monthly = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع" AND payment_date >= date("now", "-30 days")').fetchone()['total'] or 0
    weekly = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع" AND payment_date >= date("now", "-7 days")').fetchone()['total'] or 0
    daily = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع" AND payment_date >= date("now", "-1 day")').fetchone()['total'] or 0
    
    revenue_data = [
        ['إجمالي الإيرادات', 'هذا الشهر', 'هذا الأسبوع', 'اليوم'],
        [f"{total_revenue} ج.م", f"{monthly} ج.م", f"{weekly} ج.م", f"{daily} ج.م"]
    ]
    revenue_table = Table(revenue_data, colWidths=[100, 100, 100, 100])
    revenue_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#17a2b8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(revenue_table)
    
    conn.close()
    
    story.append(Spacer(1, 24))
    story.append(Paragraph("تم إنشاء هذا التقرير بواسطة نظام إدارة المهام", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, 
                    download_name=f'تقرير_شامل_{datetime.now().strftime("%Y%m%d")}.pdf', 
                    mimetype='application/pdf')

@app.route('/export_all_payments_excel')
def export_all_payments_excel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    payments = conn.execute('''
        SELECT client_payments.*, 
               clients.name as client_name, 
               clients.company_name,
               client_modules.name as module_name
        FROM client_payments
        JOIN clients ON client_payments.client_id = clients.id
        LEFT JOIN client_modules ON client_payments.module_id = client_modules.id
        ORDER BY client_payments.created_at DESC
    ''').fetchall()
    conn.close()
    
    data = []
    for p in payments:
        data.append({
            'رقم الدفعة': p['id'],
            'العميل': p['client_name'],
            'الشركة': p['company_name'] or '',
            'المديول': p['module_name'] or '-',
            'المبلغ': p['amount'],
            'تاريخ الدفع': p['payment_date'],
            'تاريخ الاستحقاق': p['due_date'] or '-',
            'طريقة الدفع': p['payment_method'],
            'الحالة': p['status'],
            'رقم الفاتورة': p['invoice_number'] or '-',
            'ملاحظات': p['notes'] or ''
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='المدفوعات')
        workbook = writer.book
        worksheet = writer.sheets['المدفوعات']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    return send_file(output, as_attachment=True, 
                    download_name=f'جميع_المدفوعات_{datetime.now().strftime("%Y%m%d")}.xlsx', 
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/export_revenue_excel')
def export_revenue_excel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    revenue_by_client = conn.execute('''
        SELECT clients.name, 
               SUM(client_payments.amount) as total,
               COUNT(client_payments.id) as count
        FROM client_payments
        JOIN clients ON client_payments.client_id = clients.id
        WHERE client_payments.status = "مدفوع"
        GROUP BY clients.id
        ORDER BY total DESC
    ''').fetchall()
    
    revenue_by_month = conn.execute('''
        SELECT strftime("%Y-%m", payment_date) as month,
               SUM(amount) as total
        FROM client_payments
        WHERE status = "مدفوع"
        GROUP BY strftime("%Y-%m", payment_date)
        ORDER BY month DESC
    ''').fetchall()
    
    total_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع"').fetchone()['total'] or 0
    conn.close()
    
    data = []
    data.append({'النوع': 'إجمالي الإيرادات', 'القيمة': f"{total_revenue} ج.م", 'ملاحظة': ''})
    data.append({'النوع': '', 'القيمة': '', 'ملاحظة': ''})
    
    for client in revenue_by_client:
        data.append({'النوع': f'العميل: {client["name"]}', 'القيمة': f"{client['total']} ج.م", 'ملاحظة': f'{client["count"]} مدفوعات'})
    
    data.append({'النوع': '', 'القيمة': '', 'ملاحظة': ''})
    data.append({'النوع': '--- الإيرادات حسب الشهر ---', 'القيمة': '', 'ملاحظة': ''})
    
    for month in revenue_by_month:
        data.append({'النوع': f'شهر {month["month"]}', 'القيمة': f"{month['total']} ج.م", 'ملاحظة': ''})
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='تقرير الإيرادات')
        workbook = writer.book
        worksheet = writer.sheets['تقرير الإيرادات']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    return send_file(output, as_attachment=True, 
                    download_name=f'تقرير_الإيرادات_{datetime.now().strftime("%Y%m%d")}.xlsx', 
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/export_revenue_pdf')
def export_revenue_pdf():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    total_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع"').fetchone()['total'] or 0
    revenue_by_client = conn.execute('''
        SELECT clients.name, 
               SUM(client_payments.amount) as total,
               COUNT(client_payments.id) as count
        FROM client_payments
        JOIN clients ON client_payments.client_id = clients.id
        WHERE client_payments.status = "مدفوع"
        GROUP BY clients.id
        ORDER BY total DESC
    ''').fetchall()
    revenue_by_month = conn.execute('''
        SELECT strftime("%Y-%m", payment_date) as month,
               SUM(amount) as total
        FROM client_payments
        WHERE status = "مدفوع"
        GROUP BY strftime("%Y-%m", payment_date)
        ORDER BY month DESC
    ''').fetchall()
    conn.close()
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], alignment=1, fontSize=16)
    
    story = []
    story.append(Paragraph("تقرير الإيرادات", title_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 24))
    
    story.append(Paragraph(f"<b>إجمالي الإيرادات: {total_revenue} ج.م</b>", styles['Normal']))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("<b>الإيرادات حسب العميل</b>", styles['Heading2']))
    if revenue_by_client:
        data = [['#', 'العميل', 'عدد المدفوعات', 'المبلغ']]
        for i, client in enumerate(revenue_by_client, 1):
            data.append([str(i), client['name'], str(client['count']), f"{client['total']} ج.م"])
        table = Table(data, colWidths=[30, 120, 80, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("لا توجد إيرادات مسجلة", styles['Normal']))
    story.append(Spacer(1, 24))
    
    story.append(Paragraph("<b>الإيرادات حسب الشهر</b>", styles['Heading2']))
    if revenue_by_month:
        data = [['الشهر', 'المبلغ']]
        for month in revenue_by_month:
            data.append([month['month'], f"{month['total']} ج.م"])
        table = Table(data, colWidths=[100, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("لا توجد إيرادات مسجلة", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, 
                    download_name=f'تقرير_الإيرادات_{datetime.now().strftime("%Y%m%d")}.pdf', 
                    mimetype='application/pdf')

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash('❌ كلمة المرور الجديدة وتأكيدها غير متطابقين', 'danger')
            return render_template('change_password.html')
        
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE id = ? AND password = ?', 
                           (session['user_id'], hash_password(current_password))).fetchone()
        
        if not user:
            flash('❌ كلمة المرور الحالية غير صحيحة', 'danger')
            conn.close()
            return render_template('change_password.html')
        
        conn.execute('UPDATE users SET password = ? WHERE id = ?', 
                    (hash_password(new_password), session['user_id']))
        conn.commit()
        conn.close()
        
        flash('✅ تم تغيير كلمة المرور بنجاح', 'success')
        log_activity(session['user_id'], 'تغيير كلمة مرور', '')
        return redirect(url_for('index'))
    
    return render_template('change_password.html')
# ============================================================
# النسخ الاحتياطي
# ============================================================

@app.route('/backup_database')
def backup_database():
    """عمل نسخة احتياطية من قاعدة البيانات"""
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    
    try:
        db_path = '/app/data/tasks.db'
        backup_dir = '/app/data/backups/'
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
            flash(f'✅ تم إنشاء النسخة الاحتياطية بنجاح: {backup_name}', 'success')
        else:
            flash('❌ قاعدة البيانات غير موجودة', 'danger')
    except Exception as e:
        flash(f'❌ خطأ: {str(e)}', 'danger')
    
    return redirect(url_for('company_settings'))

@app.route('/download_backup')
def download_backup():
    """تحميل أحدث نسخة احتياطية"""
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    
    backup_dir = '/app/data/backups/'
    if not os.path.exists(backup_dir):
        flash('❌ لا توجد نسخ احتياطية', 'danger')
        return redirect(url_for('company_settings'))
    
    backups = sorted(os.listdir(backup_dir), reverse=True)
    if not backups:
        flash('❌ لا توجد نسخ احتياطية', 'danger')
        return redirect(url_for('company_settings'))
    
    latest = os.path.join(backup_dir, backups[0])
    return send_file(latest, as_attachment=True, download_name=backups[0])
import shutil
from datetime import datetime

# ============================================================
# نسخ احتياطي تلقائي
# ============================================================

def auto_backup():
    """عمل نسخة احتياطية من قاعدة البيانات"""
    try:
        db_path = '/app/data/tasks.db'
        backup_dir = '/app/data/backups/'
        
        # تأكد من وجود مجلد النسخ الاحتياطية
        os.makedirs(backup_dir, exist_ok=True)
        
        # اسم الملف بالتاريخ
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        
        # نسخ الملف
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
            
            # حذف النسخ القديمة (احتفظ بآخر 30 نسخة)
            backups = sorted(os.listdir(backup_dir))
            if len(backups) > 30:
                for old in backups[:-30]:
                    os.remove(os.path.join(backup_dir, old))
            
            print(f"✅ تم إنشاء نسخة احتياطية: {backup_name}")
            return True
    except Exception as e:
        print(f"❌ خطأ في النسخ الاحتياطي: {str(e)}")
        return False

# ===== استدعاء النسخ الاحتياطي عند بدء التشغيل =====
# auto_backup()
# ============================================================
# استعادة البيانات من النسخة الاحتياطية
# ============================================================

import zipfile

@app.route('/restore_backup', methods=['POST'])
def restore_backup():
    """استعادة البيانات من ملف النسخة الاحتياطية"""
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('company_settings'))
    
    if 'backup_file' not in request.files:
        flash('❌ لم يتم اختيار ملف', 'danger')
        return redirect(url_for('company_settings'))
    
    file = request.files['backup_file']
    if file.filename == '':
        flash('❌ لم يتم اختيار ملف', 'danger')
        return redirect(url_for('company_settings'))
    
    if not file.filename.endswith(('.db', '.sql', '.zip')):
        flash('❌ صيغة الملف غير مدعومة. استخدم .db أو .sql أو .zip', 'danger')
        return redirect(url_for('company_settings'))
    
    try:
        # حفظ الملف المؤقت
        temp_path = os.path.join('/tmp', secure_filename(file.filename))
        file.save(temp_path)
        
        # استعادة البيانات
        if file.filename.endswith('.db'):
            # استعادة مباشرة من ملف SQLite
            import shutil
            db_path = '/app/data/tasks.db'
            shutil.copy2(temp_path, db_path)
            flash('✅ تم استعادة البيانات بنجاح من ملف .db', 'success')
            
        elif file.filename.endswith('.sql'):
            # استعادة من ملف SQL
            import sqlite3
            db_path = '/app/data/tasks.db'
            conn = sqlite3.connect(db_path)
            with open(temp_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
                conn.executescript(sql_script)
            conn.commit()
            conn.close()
            flash('✅ تم استعادة البيانات بنجاح من ملف .sql', 'success')
            
        elif file.filename.endswith('.zip'):
            # استعادة من ملف ZIP
            import zipfile
            import shutil
            extract_dir = '/tmp/restore_extract'
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # البحث عن ملف .db في المجلد المستخرج
            db_files = [f for f in os.listdir(extract_dir) if f.endswith('.db')]
            if db_files:
                db_path = '/app/data/tasks.db'
                shutil.copy2(os.path.join(extract_dir, db_files[0]), db_path)
                flash(f'✅ تم استعادة البيانات بنجاح من {db_files[0]}', 'success')
            else:
                flash('❌ لم يتم العثور على ملف قاعدة بيانات في الملف المضغوط', 'danger')
        
        # حذف الملف المؤقت
        os.remove(temp_path)
        
        # إعادة تشغيل التطبيق
        log_activity(session['user_id'], 'استعادة بيانات', 'تم استعادة البيانات من النسخة الاحتياطية')
        
    except Exception as e:
        flash(f'❌ خطأ أثناء استعادة البيانات: {str(e)}', 'danger')
    
    return redirect(url_for('company_settings'))

# ============================================================
# تشغيل التطبيق
# ============================================================
if __name__ == '__main__':
    print("🚀 جاري تشغيل السيرفر...")
    print("📍 افتح المتصفح على: http://127.0.0.1:5000")
    print("👤 حسابات تجريبية:")
    print("   Fahd01 / 1234 (مدير)")
    print("   employee1 / 1234 (موظف)")
    print("   viewer1 / 1234 (مراقب)")
    app.run(debug=True, host='0.0.0.0', port=5000)
