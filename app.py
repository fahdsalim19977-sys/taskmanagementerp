# app.py
import os
import sys
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from models import get_db, init_db, hash_password
from config import Config
from translations import get_text
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import pandas as pd
import json
import sqlite3
import shutil
import zipfile

# ===== إعدادات التسجيل =====
logging.basicConfig(level=logging.DEBUG)
print("🚀 بدء تشغيل التطبيق...")

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
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'contracts'), exist_ok=True)
print(f"📁 مجلدات التحميل جاهزة: {app.config['UPLOAD_FOLDER']}")

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
def log_activity(user_id, action, details=None):
    try:
        conn = get_db()
        conn.execute('INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)', 
                     (user_id, action, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ خطأ في تسجيل النشاط: {e}")

def check_role(allowed_roles):
    if 'user_id' not in session:
        return False
    conn = get_db()
    user = conn.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return user and user['role'] in allowed_roles

def get_company_settings():
    try:
        conn = get_db()
        settings = conn.execute('SELECT * FROM company_settings LIMIT 1').fetchone()
        conn.close()
        return settings
    except Exception as e:
        print(f"❌ خطأ في جلب إعدادات الشركة: {e}")
        return None

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
print("🔄 جاري تهيئة قاعدة البيانات...")
try:
    init_db()
    print("✅ تم تهيئة قاعدة البيانات بنجاح")
except Exception as e:
    print(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# Health Check (لـ Railway)
# ============================================================
@app.route('/health')
def health():
    """Health check endpoint for Railway"""
    return jsonify({"status": "ok", "message": "Application is running"}), 200

# ============================================================
# الصفحة الرئيسية
# ============================================================
@app.route('/')
def index():
    print("🔍 Index route called")
    try:
        if 'user_id' not in session:
            print("👤 No user in session, redirecting to login")
            return redirect(url_for('login'))
        
        print(f"👤 User: {session.get('user_name')} (ID: {session.get('user_id')})")
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
                             settings=settings)
    except Exception as e:
        print(f"❌ خطأ في Index: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ============================================================
# تسجيل الدخول والخروج
# ============================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    print("🔍 Login route called")
    try:
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            print(f"👤 محاولة تسجيل دخول: {username}")
            
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
                
                print(f"✅ تسجيل دخول ناجح: {user['name']}")
                flash(f'مرحباً {user["name"]}! 👋', 'success')
                
                if user['role'] == 'مدير':
                    return redirect(url_for('index'))
                elif user['role'] == 'موظف':
                    return redirect(url_for('tasks'))
                else:
                    return redirect(url_for('clients'))
            else:
                print(f"❌ فشل تسجيل الدخول: {username}")
                flash('❌ اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
        
        settings = get_company_settings()
        return render_template('login.html', settings=settings)
    except Exception as e:
        print(f"❌ خطأ في Login: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/logout')
def logout():
    """تسجيل الخروج"""
    try:
        if 'user_id' in session:
            log_activity(session['user_id'], 'تسجيل خروج', '')
        session.clear()
        flash('✅ تم تسجيل الخروج بنجاح', 'success')
        return redirect(url_for('login'))
    except Exception as e:
        print(f"❌ خطأ في Logout: {e}")
        session.clear()
        return redirect(url_for('login'))

# ============================================================
# باقي المسارات (Tasks, Clients, Contracts, etc.)
# ============================================================

# ===== إدارة المستخدمين =====
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

# ===== إدارة العملاء =====
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

# ===== عقود العملاء =====
@app.route('/contracts')
def contracts():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    contracts_list = conn.execute('''
        SELECT client_contracts.*, 
               clients.name as client_name,
               clients.company_name,
               users.name as created_by_name
        FROM client_contracts
        JOIN clients ON client_contracts.client_id = clients.id
        JOIN users ON client_contracts.created_by = users.id
        ORDER BY client_contracts.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('contracts.html', contracts=contracts_list)

@app.route('/add_contract', methods=['GET', 'POST'])
def add_contract():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    clients = conn.execute('SELECT id, name, company_name FROM clients ORDER BY name').fetchall()
    
    if request.method == 'POST':
        client_id = request.form['client_id']
        contract_number = request.form['contract_number']
        title = request.form['title']
        description = request.form.get('description', '')
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        contract_value = request.form.get('contract_value', 0)
        status = request.form['status']
        notes = request.form.get('notes', '')
        attachment_description = request.form.get('attachment_description', '')
        
        check = conn.execute('SELECT * FROM client_contracts WHERE contract_number = ?', (contract_number,)).fetchone()
        if check:
            flash('❌ رقم العقد موجود مسبقاً', 'danger')
            conn.close()
            return render_template('add_contract.html', clients=clients)
        
        cursor = conn.execute('''
            INSERT INTO client_contracts 
            (client_id, contract_number, title, description, start_date, end_date, 
             contract_value, status, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, contract_number, title, description, start_date, end_date, 
              contract_value, status, notes, session['user_id']))
        contract_id = cursor.lastrowid
        conn.commit()
        
        # ===== معالجة المرفقات =====
        files = request.files.getlist('attachments')
        uploaded_count = 0
        
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                name_parts = filename.rsplit('.', 1)
                if len(name_parts) > 1:
                    filename = f"{name_parts[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{name_parts[1]}"
                else:
                    filename = f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                attachments_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'contracts', str(contract_id))
                os.makedirs(attachments_folder, exist_ok=True)
                file_path = os.path.join(attachments_folder, filename)
                file.save(file_path)
                
                file_size = os.path.getsize(file_path)
                conn.execute('''
                    INSERT INTO contract_attachments 
                    (contract_id, file_name, file_path, file_size, file_type, uploaded_by, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (contract_id, filename, file_path, file_size, file.content_type, 
                      session['user_id'], attachment_description or filename))
                uploaded_count += 1
        
        conn.commit()
        conn.close()
        
        flash(f'✅ تم إضافة العقد بنجاح مع {uploaded_count} مرفق(ات)', 'success')
        log_activity(session['user_id'], 'إضافة عقد', f'أضاف عقد {contract_number} مع {uploaded_count} مرفق')
        return redirect(url_for('contracts'))
    
    conn.close()
    return render_template('add_contract.html', clients=clients)

@app.route('/edit_contract/<int:contract_id>', methods=['GET', 'POST'])
def edit_contract(contract_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    contract = conn.execute('SELECT * FROM client_contracts WHERE id = ?', (contract_id,)).fetchone()
    if not contract:
        flash('❌ العقد غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts'))
    
    clients = conn.execute('SELECT id, name, company_name FROM clients ORDER BY name').fetchall()
    
    if request.method == 'POST':
        client_id = request.form['client_id']
        contract_number = request.form['contract_number']
        title = request.form['title']
        description = request.form.get('description', '')
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        contract_value = request.form.get('contract_value', 0)
        status = request.form['status']
        notes = request.form.get('notes', '')
        
        check = conn.execute('''
            SELECT * FROM client_contracts 
            WHERE contract_number = ? AND id != ?
        ''', (contract_number, contract_id)).fetchone()
        if check:
            flash('❌ رقم العقد موجود مسبقاً', 'danger')
            conn.close()
            return render_template('edit_contract.html', contract=contract, clients=clients)
        
        conn.execute('''
            UPDATE client_contracts SET 
                client_id = ?, contract_number = ?, title = ?, description = ?,
                start_date = ?, end_date = ?, contract_value = ?, status = ?, notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (client_id, contract_number, title, description, start_date, end_date, 
              contract_value, status, notes, contract_id))
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث العقد بنجاح', 'success')
        log_activity(session['user_id'], 'تحديث عقد', f'حدث عقد {contract_number}')
        return redirect(url_for('contracts'))
    
    conn.close()
    return render_template('edit_contract.html', contract=contract, clients=clients)

@app.route('/delete_contract/<int:contract_id>', methods=['POST'])
def delete_contract(contract_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    contract = conn.execute('SELECT * FROM client_contracts WHERE id = ?', (contract_id,)).fetchone()
    if not contract:
        flash('❌ العقد غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts'))
    
    conn.execute('DELETE FROM client_contracts WHERE id = ?', (contract_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف العقد بنجاح', 'success')
    log_activity(session['user_id'], 'حذف عقد', f'حذف عقد {contract["contract_number"]}')
    return redirect(url_for('contracts'))

@app.route('/contract/<int:contract_id>/attachments')
def contract_attachments(contract_id):
    """عرض جميع مرفقات العقد"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    contract = conn.execute('SELECT * FROM client_contracts WHERE id = ?', (contract_id,)).fetchone()
    if not contract:
        flash('❌ العقد غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts'))
    
    attachments = conn.execute('''
        SELECT contract_attachments.*, users.name as uploaded_by_name
        FROM contract_attachments
        JOIN users ON contract_attachments.uploaded_by = users.id
        WHERE contract_attachments.contract_id = ?
        ORDER BY contract_attachments.created_at DESC
    ''', (contract_id,)).fetchall()
    conn.close()
    
    return render_template('contract_attachments.html', 
                         contract=contract, 
                         attachments=attachments)

# ===== مرفقات العقود =====

@app.route('/add_contract_attachment/<int:contract_id>', methods=['POST'])
def add_contract_attachment(contract_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    contract = conn.execute('SELECT * FROM client_contracts WHERE id = ?', (contract_id,)).fetchone()
    if not contract:
        flash('❌ العقد غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts'))
    
    if 'attachment' not in request.files:
        flash('❌ لم يتم اختيار ملف', 'danger')
        conn.close()
        return redirect(url_for('contract_details', contract_id=contract_id))
    
    file = request.files['attachment']
    if file.filename == '':
        flash('❌ لم يتم اختيار ملف', 'danger')
        conn.close()
        return redirect(url_for('contract_details', contract_id=contract_id))
    
    description = request.form.get('description', '')
    
    filename = secure_filename(file.filename)
    name_parts = filename.rsplit('.', 1)
    if len(name_parts) > 1:
        filename = f"{name_parts[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{name_parts[1]}"
    else:
        filename = f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    attachments_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'contracts', str(contract_id))
    os.makedirs(attachments_folder, exist_ok=True)
    file_path = os.path.join(attachments_folder, filename)
    file.save(file_path)
    
    file_size = os.path.getsize(file_path)
    conn.execute('''
        INSERT INTO contract_attachments 
        (contract_id, file_name, file_path, file_size, file_type, uploaded_by, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (contract_id, filename, file_path, file_size, file.content_type, 
          session['user_id'], description))
    conn.commit()
    conn.close()
    
    flash('✅ تم رفع المرفق بنجاح', 'success')
    log_activity(session['user_id'], 'رفع مرفق عقد', f'رفع {filename} للعقد {contract["contract_number"]}')
    return redirect(url_for('contract_details', contract_id=contract_id))

@app.route('/download_contract_attachment/<int:attachment_id>')
def download_contract_attachment(attachment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    attachment = conn.execute('SELECT * FROM contract_attachments WHERE id = ?', (attachment_id,)).fetchone()
    if not attachment:
        flash('❌ المرفق غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts'))
    
    conn.close()
    
    if os.path.exists(attachment['file_path']):
        return send_file(attachment['file_path'], 
                       as_attachment=True, 
                       download_name=attachment['file_name'])
    else:
        flash('❌ الملف غير موجود على السيرفر', 'danger')
        return redirect(request.referrer or url_for('contracts'))

@app.route('/delete_contract_attachment/<int:attachment_id>', methods=['POST'])
def delete_contract_attachment(attachment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    attachment = conn.execute('SELECT * FROM contract_attachments WHERE id = ?', (attachment_id,)).fetchone()
    if not attachment:
        flash('❌ المرفق غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts'))
    
    if os.path.exists(attachment['file_path']):
        try:
            os.remove(attachment['file_path'])
        except Exception as e:
            print(f"Error deleting file: {e}")
    
    conn.execute('DELETE FROM contract_attachments WHERE id = ?', (attachment_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف المرفق بنجاح', 'success')
    log_activity(session['user_id'], 'حذف مرفق عقد', f'حذف {attachment["file_name"]}')
    return redirect(request.referrer or url_for('contracts'))

# ===== باقي المسارات (Tasks, Trainers, etc.) =====
# ... أضف بقية المسارات هنا ...

# ============================================================
# تشغيل التطبيق
# ============================================================
if __name__ == '__main__':
    print("🚀 جاري تشغيل السيرفر...")
    print("📍 افتح المتصفح على: http://127.0.0.1:5000")
    print("👤 حسابات تجريبية:")
    print("   Adminerp / 1234 (مدير)")
    print("   Fahd01 / 1234 (مدير)")
    print("   employee1 / 1234 (موظف)")
    print("   viewer1 / 1234 (مراقب)")
    app.run(debug=True, host='0.0.0.0', port=5000)
