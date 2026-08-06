# routes/settings.py
from flask import render_template, request, redirect, url_for, session, flash, send_file
import os
import shutil
import sqlite3
from datetime import datetime
from werkzeug.utils import secure_filename
from models import get_db
from routes import settings_bp
from utils import check_role, log_activity, get_company_settings
from config import Config

@settings_bp.route('/company_settings', methods=['GET', 'POST'])
def company_settings():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('settings.company_settings'))  # ✅ تغيير
    
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
        return redirect(url_for('settings.company_settings'))  # ✅ تغيير
    
    conn.close()
    return render_template('company_settings.html', settings=settings)


@settings_bp.route('/upload_logo', methods=['POST'])
def upload_logo():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('settings.company_settings'))  # ✅ تغيير
    
    if 'logo' not in request.files:
        flash('❌ لم يتم اختيار صورة', 'danger')
        return redirect(url_for('settings.company_settings'))  # ✅ تغيير
    
    file = request.files['logo']
    if file.filename == '':
        flash('❌ لم يتم اختيار صورة', 'danger')
        return redirect(url_for('settings.company_settings'))  # ✅ تغيير
    
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
    
    return redirect(url_for('settings.company_settings'))  # ✅ تغيير


@settings_bp.route('/upload_favicon', methods=['POST'])
def upload_favicon():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('settings.company_settings'))  # ✅ تغيير
    
    if 'favicon' not in request.files:
        flash('❌ لم يتم اختيار صورة', 'danger')
        return redirect(url_for('settings.company_settings'))  # ✅ تغيير
    
    file = request.files['favicon']
    if file.filename == '':
        flash('❌ لم يتم اختيار صورة', 'danger')
        return redirect(url_for('settings.company_settings'))  # ✅ تغيير
    
    if file:
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'png'
        filename = f"favicon.{ext}"
        file_path = os.path.join('static', filename)
        file.save(file_path)
        
        conn = get_db()
        conn.execute('UPDATE company_settings SET favicon_path = ?', (filename,))
        conn.commit()
        conn.close()
        
        flash('✅ تم رفع أيقونة الموقع بنجاح', 'success')
        log_activity(session['user_id'], 'رفع أيقونة موقع', f'رفع {filename}')
    
    return redirect(url_for('settings.company_settings'))  # ✅ تغيير


@settings_bp.route('/reset_sequence', methods=['POST'])
def reset_sequence():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('settings.company_settings'))  # ✅ تغيير
    
    try:
        conn = get_db()
        
        tables = [
            'client_contracts', 'clients', 'client_payments', 'tasks', 'trainers',
            'contract_payments', 'contract_attachments', 'client_modules', 'meetings'
        ]
        
        for table in tables:
            conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
        
        conn.commit()
        conn.close()
        
        flash('✅ تم إعادة ضبط الترقيم لجميع الجداول بنجاح', 'success')
        log_activity(session['user_id'], 'إعادة ضبط الترقيم', '')
    except Exception as e:
        flash(f'❌ خطأ: {str(e)}', 'danger')
    
    return redirect(url_for('settings.company_settings'))  # ✅ تغيير


@settings_bp.route('/delete_all_data', methods=['POST'])
def delete_all_data():
    """حذف جميع البيانات من النظام (للمدير فقط)"""
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('settings.company_settings'))  # ✅ تغيير
    
    confirm_text = request.form.get('confirm_text', '')
    if confirm_text != 'تأكيد':
        flash('❌ لم تقم بتأكيد الحذف بشكل صحيح', 'danger')
        return redirect(url_for('settings.company_settings'))  # ✅ تغيير
    
    try:
        conn = get_db()
        
        # عمل نسخة احتياطية قبل الحذف
        backup_dir = '/app/data/backups/'
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_before_delete_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        
        db_path = '/app/data/tasks.db'
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
            print(f"✅ نسخة احتياطية قبل الحذف: {backup_name}")
        
        tables = [
            'contract_payments', 'contract_attachments', 'contract_modules',
            'client_contracts', 'client_payments', 'payment_installments',
            'client_modules', 'task_updates', 'tasks', 'meeting_reminders',
            'meetings', 'client_trainers', 'clients', 'trainers',
            'notifications', 'activity_log', 'login_attempts'
        ]
        
        for table in tables:
            try:
                conn.execute(f"DELETE FROM {table}")
                print(f"✅ تم مسح جدول: {table}")
            except sqlite3.OperationalError as e:
                if 'no such table' in str(e):
                    print(f"⚠️ الجدول {table} غير موجود")
                else:
                    print(f"❌ خطأ في {table}: {e}")
        
        for table in tables:
            try:
                conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
            except:
                pass
        
        conn.commit()
        conn.close()
        
        flash(f'✅ تم مسح جميع البيانات بنجاح! (نسخة احتياطية: {backup_name})', 'success')
        log_activity(session['user_id'], 'مسح جميع البيانات', f'تم مسح جميع البيانات، النسخة الاحتياطية: {backup_name}')
        
    except Exception as e:
        flash(f'❌ خطأ أثناء مسح البيانات: {str(e)}', 'danger')
        print(f"❌ خطأ: {e}")
    
    return redirect(url_for('settings.company_settings'))  # ✅ تغيير