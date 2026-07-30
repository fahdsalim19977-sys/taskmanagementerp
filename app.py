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
    return {
        't': t,
        'get_lang': get_lang,
        'datetime': datetime
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
# باقي الدوال...
# ============================================================
# ... ضع باقي دوالك هنا (clients, tasks, payments, etc.)

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
