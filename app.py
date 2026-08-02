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
import shutil
import zipfile

# ===== إعدادات IIS =====
if os.name == 'nt':
    sys.path.insert(0, os.path.dirname(__file__))

# ============================================================
# إنشاء التطبيق
# ============================================================
app = Flask(__name__)
app.config.from_object(Config)

# ===== مفتاح سري للجلسات =====
app.secret_key = 's7f8g9h0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9'

# التأكد من وجود مجلدات
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'contracts'), exist_ok=True)

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
# (جميع المسارات الأخرى من ملفك الأصلي)
# ============================================================
# ... (ضع هنا جميع المسارات الأخرى مثل users, clients, tasks, etc.)
# ... (باستثناء العقود لأننا سنضعها أدناه)

# ============================================================
# عقود العملاء (بالإصدار الجديد مع الدفعات)
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
        total_amount = request.form.get('total_amount', 0)
        attachment_description = request.form.get('attachment_description', '')
        
        # التحقق من رقم العقد
        check = conn.execute('SELECT * FROM client_contracts WHERE contract_number = ?', (contract_number,)).fetchone()
        if check:
            flash('❌ رقم العقد موجود مسبقاً', 'danger')
            conn.close()
            return render_template('add_contract.html', clients=clients)
        
        # إضافة العقد
        cursor = conn.execute('''
            INSERT INTO client_contracts 
            (client_id, contract_number, title, description, start_date, end_date, 
             contract_value, total_amount, status, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, contract_number, title, description, start_date, end_date, 
              contract_value, total_amount, status, notes, session['user_id']))
        contract_id = cursor.lastrowid
        
        # ===== إنشاء الدفعات =====
        installment_count = int(request.form.get('installment_count', 0))
        
        for i in range(1, installment_count + 1):
            amount = request.form.get(f'installment_amount_{i}', 0)
            due_date = request.form.get(f'installment_due_date_{i}', '')
            note = request.form.get(f'installment_notes_{i}', '')
            
            if due_date and float(amount) > 0:
                conn.execute('''
                    INSERT INTO contract_payments 
                    (contract_id, installment_number, amount, due_date, notes)
                    VALUES (?, ?, ?, ?, ?)
                ''', (contract_id, i, amount, due_date, note))
        
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
        
        flash(f'✅ تم إضافة العقد بنجاح مع {uploaded_count} مرفق و {installment_count} دفعة', 'success')
        log_activity(session['user_id'], 'إضافة عقد', f'أضاف عقد {contract_number}')
        return redirect(url_for('contracts'))
    
    conn.close()
    return render_template('add_contract.html', clients=clients)  # ✅ قوس واحد فقط

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

@app.route('/contract/<int:contract_id>')
def contract_details(contract_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    
    # جلب معلومات العقد
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
    
    # جلب المرفقات
    attachments = conn.execute('''
        SELECT contract_attachments.*, users.name as uploaded_by_name
        FROM contract_attachments
        JOIN users ON contract_attachments.uploaded_by = users.id
        WHERE contract_attachments.contract_id = ?
        ORDER BY contract_attachments.created_at DESC
    ''', (contract_id,)).fetchall()
    
    # ===== جلب دفعات العقد =====
    payments = conn.execute('''
        SELECT * FROM contract_payments 
        WHERE contract_id = ?
        ORDER BY installment_number ASC
    ''', (contract_id,)).fetchall()
    
    conn.close()
    
    # ===== طباعة للتصحيح =====
    print(f"📎 عدد المرفقات للعقد {contract_id}: {len(attachments)}")
    for att in attachments:
        print(f"   - {att['file_name']} ({att['file_size']} bytes)")
    
    return render_template('contract_details.html', 
                         contract=contract,
                         contract_attachments=attachments,
                         contract_payments=payments)

# ===== مرفقات العقود =====

@app.route('/add_contract_attachment/<int:contract_id>', methods=['POST'])
def add_contract_attachment(contract_id):
    """رفع مرفق جديد للعقد"""
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
    
    # حفظ الملف
    filename = secure_filename(file.filename)
    name_parts = filename.rsplit('.', 1)
    if len(name_parts) > 1:
        filename = f"{name_parts[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{name_parts[1]}"
    else:
        filename = f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # مجلد خاص بمرفقات العقود
    attachments_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'contracts', str(contract_id))
    os.makedirs(attachments_folder, exist_ok=True)
    file_path = os.path.join(attachments_folder, filename)
    file.save(file_path)
    
    # حفظ في قاعدة البيانات
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
    """تحميل مرفق العقد"""
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
    """حذف مرفق العقد"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    attachment = conn.execute('SELECT * FROM contract_attachments WHERE id = ?', (attachment_id,)).fetchone()
    if not attachment:
        flash('❌ المرفق غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts'))
    
    # حذف الملف الفعلي
    if os.path.exists(attachment['file_path']):
        try:
            os.remove(attachment['file_path'])
        except Exception as e:
            print(f"Error deleting file: {e}")
    
    # حذف من قاعدة البيانات
    conn.execute('DELETE FROM contract_attachments WHERE id = ?', (attachment_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف المرفق بنجاح', 'success')
    log_activity(session['user_id'], 'حذف مرفق عقد', f'حذف {attachment["file_name"]}')
    return redirect(request.referrer or url_for('contracts'))

@app.route('/mark_payment_paid/<int:payment_id>', methods=['POST'])
def mark_payment_paid(payment_id):
    """تحديد دفعة كمدفوعة"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    
    # جلب الدفعة
    payment = conn.execute('SELECT * FROM contract_payments WHERE id = ?', (payment_id,)).fetchone()
    if not payment:
        flash('❌ الدفعة غير موجودة', 'danger')
        conn.close()
        return redirect(url_for('contracts'))
    
    # تحديث حالة الدفعة
    conn.execute('''
        UPDATE contract_payments 
        SET status = 'مدفوعة', 
            payment_date = date('now'),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (payment_id,))
    
    # تحديث المبلغ المدفوع في العقد
    contract_id = payment['contract_id']
    paid_amount = conn.execute('''
        SELECT SUM(amount) as total FROM contract_payments 
        WHERE contract_id = ? AND status = 'مدفوعة'
    ''', (contract_id,)).fetchone()['total'] or 0
    
    # تحديث حالة العقد
    contract = conn.execute('SELECT total_amount FROM client_contracts WHERE id = ?', (contract_id,)).fetchone()
    total = contract['total_amount'] or 0
    
    if paid_amount >= total:
        payment_status = 'مدفوع بالكامل'
    elif paid_amount > 0:
        payment_status = 'مدفوع جزئياً'
    else:
        payment_status = 'غير مدفوع'
    
    conn.execute('''
        UPDATE client_contracts 
        SET paid_amount = ?, payment_status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (paid_amount, payment_status, contract_id))
    
    conn.commit()
    conn.close()
    
    flash('✅ تم تسجيل الدفعة كمدفوعة', 'success')
    log_activity(session['user_id'], 'تسجيل دفعة', f'تم استلام دفعة {payment["installment_number"]}')
    return redirect(request.referrer or url_for('contracts'))

# ============================================================
# (باقي المسارات الأخرى من ملفك الأصلي)
# ============================================================

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
