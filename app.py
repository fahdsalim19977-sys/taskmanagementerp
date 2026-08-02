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

# ===== إعدادات التسجيل =====
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
print("=" * 60)
print("🚀 بدء تشغيل التطبيق...")
print("=" * 60)

# ===== إعدادات IIS =====
if os.name == 'nt':
    sys.path.insert(0, os.path.dirname(__file__))

# ============================================================
# إنشاء التطبيق
# ============================================================
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = 's7f8g9h0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9'

# التأكد من وجود مجلدات
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'contracts'), exist_ok=True)

print("✅ مجلدات التحميل جاهزة")

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
    try:
        conn = get_db()
        conn.execute('INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)', 
                     (user_id, action, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ خطأ في log_activity: {e}")

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
        print(f"❌ خطأ في get_company_settings: {e}")
        return None

def get_trainers():
    conn = get_db()
    trainers = conn.execute('''
        SELECT id, name FROM trainers 
        WHERE is_active = 1
        ORDER BY name
    ''').fetchall()
    conn.close()
    return trainers

# ============================================================
# دوال الأمان
# ============================================================
import re
import hashlib

def is_strong_password(password):
    if len(password) < 8:
        return False, "كلمة المرور يجب أن تكون 8 أحرف على الأقل"
    if not re.search(r'[A-Z]', password):
        return False, "كلمة المرور يجب أن تحتوي على حرف كبير (A-Z)"
    if not re.search(r'[a-z]', password):
        return False, "كلمة المرور يجب أن تحتوي على حرف صغير (a-z)"
    if not re.search(r'[0-9]', password):
        return False, "كلمة المرور يجب أن تحتوي على رقم (0-9)"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "كلمة المرور يجب أن تحتوي على رمز خاص (!@#$%^&*)"
    return True, "كلمة مرور قوية"

# ============================================================
# Health Check (لـ Railway)
# ============================================================
@app.route('/health')
def health():
    print("✅ Health check called!")
    return jsonify({"status": "ok", "message": "Application is running"}), 200

# ============================================================
# معالج الأخطاء العام
# ============================================================
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    print("=" * 60)
    print("❌ خطأ غير متوقع:")
    print("=" * 60)
    traceback.print_exc()
    print("=" * 60)
    return jsonify({
        "error": str(e),
        "traceback": traceback.format_exc()
    }), 500

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
# تسجيل الدخول
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
        total_payments = conn.execute('SELECT COUNT(*) as count FROM client_payments').fetchone()['count'] or 0
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
                             total_payments=total_payments,
                             upcoming_meetings=upcoming_meetings,
                             total_revenue=total_revenue,
                             overdue_list=overdue_list,
                             recent_activity=recent_activity,
                             settings=settings)
    except Exception as e:
        print(f"❌ خطأ في Index: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ============================================================
# العملاء
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

# ============================================================
# العقود
# ============================================================
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
        
        # معالجة المرفقات
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
        
        check = conn.execute('SELECT * FROM client_contracts WHERE contract_number = ? AND id != ?', 
                           (contract_number, contract_id)).fetchone()
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

@app.route('/contract/<int:contract_id>')
def contract_details(contract_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    contract = conn.execute('''
        SELECT client_contracts.*, 
               clients.name as client_name,
               clients.company_name,
               clients.phone as client_phone,
               clients.email as client_email,
               users.name as created_by_name
        FROM client_contracts
        JOIN clients ON client_contracts.client_id = clients.id
        JOIN users ON client_contracts.created_by = users.id
        WHERE client_contracts.id = ?
    ''', (contract_id,)).fetchone()
    
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
    
    return render_template('contract_details.html', 
                         contract=contract,
                         contract_attachments=attachments)

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

@app.route('/contract/<int:contract_id>/attachments')
def contract_attachments(contract_id):
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

# ============================================================
# المهام
# ============================================================
@app.route('/tasks')
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    task_list = conn.execute('''
        SELECT tasks.*, clients.name as client_name, clients.company_name, users.name as assigned_name 
        FROM tasks 
        JOIN clients ON tasks.client_id = clients.id 
        JOIN users ON tasks.assigned_to = users.id 
        ORDER BY tasks.due_date ASC
    ''').fetchall()
    conn.close()
    return render_template('tasks.html', tasks=task_list, today=datetime.now().date())

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

# ============================================================
# المدفوعات
# ============================================================
@app.route('/all_payments')
def all_payments():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    payments = conn.execute('''
        SELECT client_payments.*, 
               clients.name as client_name, 
               clients.company_name,
               users.name as created_by_name
        FROM client_payments
        LEFT JOIN clients ON client_payments.client_id = clients.id
        LEFT JOIN users ON client_payments.created_by = users.id
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
    
    return render_template('all_payments.html', payments=payments, stats=stats)

# ============================================================
# تغيير كلمة المرور
# ============================================================
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
