# routes/backups.py
from flask import render_template, request, redirect, url_for, session, flash, send_file, jsonify
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime
from werkzeug.utils import secure_filename
from routes import backups_bp
from utils import check_role, log_activity

@backups_bp.route('/backup_database')
def backup_database():
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
    
    return redirect(url_for('settings_bp.company_settings'))

@backups_bp.route('/download_backup')
def download_backup():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    
    backup_dir = '/app/data/backups/'
    if not os.path.exists(backup_dir):
        flash('❌ لا توجد نسخ احتياطية', 'danger')
        return redirect(url_for('settings_bp.company_settings'))
    
    backups = sorted(os.listdir(backup_dir), reverse=True)
    if not backups:
        flash('❌ لا توجد نسخ احتياطية', 'danger')
        return redirect(url_for('settings_bp.company_settings'))
    
    latest = os.path.join(backup_dir, backups[0])
    return send_file(latest, as_attachment=True, download_name=backups[0])

@backups_bp.route('/restore_backup', methods=['POST'])
def restore_backup():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('settings_bp.company_settings'))
    
    if 'backup_file' not in request.files:
        flash('❌ لم يتم اختيار ملف', 'danger')
        return redirect(url_for('settings_bp.company_settings'))
    
    file = request.files['backup_file']
    if file.filename == '':
        flash('❌ لم يتم اختيار ملف', 'danger')
        return redirect(url_for('settings_bp.company_settings'))
    
    if not file.filename.endswith(('.db', '.sql', '.zip')):
        flash('❌ صيغة الملف غير مدعومة. استخدم .db أو .sql أو .zip', 'danger')
        return redirect(url_for('settings_bp.company_settings'))
    
    try:
        temp_path = os.path.join('/tmp', secure_filename(file.filename))
        file.save(temp_path)
        
        if file.filename.endswith('.db'):
            db_path = '/app/data/tasks.db'
            shutil.copy2(temp_path, db_path)
            flash('✅ تم استعادة البيانات بنجاح من ملف .db', 'success')
            
        elif file.filename.endswith('.sql'):
            db_path = '/app/data/tasks.db'
            conn = sqlite3.connect(db_path)
            with open(temp_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
                conn.executescript(sql_script)
            conn.commit()
            conn.close()
            flash('✅ تم استعادة البيانات بنجاح من ملف .sql', 'success')
            
        elif file.filename.endswith('.zip'):
            extract_dir = '/tmp/restore_extract'
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            db_files = [f for f in os.listdir(extract_dir) if f.endswith('.db')]
            if db_files:
                db_path = '/app/data/tasks.db'
                shutil.copy2(os.path.join(extract_dir, db_files[0]), db_path)
                flash(f'✅ تم استعادة البيانات بنجاح من {db_files[0]}', 'success')
            else:
                flash('❌ لم يتم العثور على ملف قاعدة بيانات في الملف المضغوط', 'danger')
        
        os.remove(temp_path)
        log_activity(session['user_id'], 'استعادة بيانات', 'تم استعادة البيانات من النسخة الاحتياطية')
        
    except Exception as e:
        flash(f'❌ خطأ أثناء استعادة البيانات: {str(e)}', 'danger')
    
    return redirect(url_for('settings_bp.company_settings'))

@backups_bp.route('/api/backup/now')
def api_backup_now():
    """إنشاء نسخة احتياطية فورية عبر API"""
    if not check_role(['مدير']):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        import subprocess
        result = subprocess.run(['python', 'backup_scheduler.py', '--once'], 
                               capture_output=True, text=True)
        return jsonify({
            'status': 'success',
            'message': 'تم إنشاء النسخة الاحتياطية',
            'output': result.stdout
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500