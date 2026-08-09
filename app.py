# app.py
import os
from flask import Flask, render_template, redirect, url_for, session, flash, jsonify, request
from config import Config
from models import init_db, get_db
from utils import get_company_settings, get_lang, t, log_activity
from datetime import datetime

# ===== إنشاء التطبيق =====
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = 's7f8g9h0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9'

# ===== مجلدات =====
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'contracts'), exist_ok=True)

# ===== قاعدة البيانات =====
init_db()

# ===== تسجيل Blueprints =====
from routes import (
    auth_bp, users_bp, clients_bp, trainers_bp, tasks_bp,
    contracts_bp, payments_bp, modules_bp, meetings_bp,
    reports_bp, settings_bp, backups_bp
)

app.register_blueprint(auth_bp)
app.register_blueprint(users_bp)
app.register_blueprint(clients_bp)
app.register_blueprint(trainers_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(contracts_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(modules_bp)
app.register_blueprint(meetings_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(backups_bp)

# ===== دوال السياق =====
@app.context_processor
def utility_processor():
    settings = get_company_settings()
    return {
        't': t,
        'get_lang': get_lang,
        'datetime': datetime,
        'settings': settings
    }

# ===== الصفحة الرئيسية =====
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    # إحصائيات المهام
    total_tasks = conn.execute('SELECT COUNT(*) as count FROM tasks').fetchone()['count']
    completed_tasks = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "مكتملة"').fetchone()['count']
    overdue_tasks = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE due_date < date("now") AND status != "مكتملة"').fetchone()['count']
    in_progress = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "قيد التنفيذ"').fetchone()['count']
    total_clients = conn.execute('SELECT COUNT(*) as count FROM clients').fetchone()['count']
    total_users = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
    upcoming_meetings = conn.execute('SELECT COUNT(*) as count FROM meetings WHERE date(meeting_date) >= date("now") AND status = "مجدول"').fetchone()['count']
    total_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع"').fetchone()['total'] or 0
    total_payments = conn.execute('SELECT COUNT(*) as count FROM client_payments').fetchone()['count'] or 0
    
    # إحصائيات العقود
    total_contracts = conn.execute('SELECT COUNT(*) as count FROM client_contracts').fetchone()['count'] or 0
    contracts_paid_full = conn.execute('SELECT COUNT(*) as count FROM client_contracts WHERE payment_status = "مدفوع بالكامل"').fetchone()['count'] or 0
    contracts_partial = conn.execute('SELECT COUNT(*) as count FROM client_contracts WHERE payment_status = "مدفوع جزئيا"').fetchone()['count'] or 0
    contracts_unpaid = conn.execute('SELECT COUNT(*) as count FROM client_contracts WHERE payment_status = "غير مدفوع"').fetchone()['count'] or 0
    contracts_unpaid_amount = conn.execute('SELECT SUM(total_amount - paid_amount) as total FROM client_contracts WHERE payment_status != "مدفوع بالكامل"').fetchone()['total'] or 0
    contracts_paid_percent = round((contracts_paid_full / total_contracts * 100) if total_contracts > 0 else 0, 1)
    contracts_partial_due = conn.execute('SELECT SUM(total_amount - paid_amount) as total FROM client_contracts WHERE payment_status = "مدفوع جزئيا"').fetchone()['total'] or 0
    
    # آخر 5 عقود
    recent_contracts = conn.execute('''
        SELECT client_contracts.*, clients.name as client_name
        FROM client_contracts
        JOIN clients ON client_contracts.client_id = clients.id
        ORDER BY client_contracts.created_at DESC LIMIT 5
    ''').fetchall()
    
    # الدفعات المستحقة هذا الشهر
    current_month = datetime.now().strftime('%Y-%m')
    due_this_month = conn.execute('''
        SELECT contract_payments.*, client_contracts.contract_number,
               clients.name as client_name
        FROM contract_payments
        JOIN client_contracts ON contract_payments.contract_id = client_contracts.id
        JOIN clients ON client_contracts.client_id = clients.id
        WHERE contract_payments.status IN ('مستحقة', 'مدفوعة جزئيا')
        AND strftime('%Y-%m', contract_payments.due_date) = ?
        ORDER BY contract_payments.due_date ASC
    ''', (current_month,)).fetchall()
    
    # الدفعات المتأخرة
    overdue_payments = conn.execute('''
        SELECT contract_payments.*, client_contracts.contract_number,
               clients.name as client_name
        FROM contract_payments
        JOIN client_contracts ON contract_payments.contract_id = client_contracts.id
        JOIN clients ON client_contracts.client_id = clients.id
        WHERE contract_payments.status IN ('مستحقة', 'مدفوعة جزئيا')
        AND contract_payments.due_date < date('now')
        ORDER BY contract_payments.due_date ASC
    ''').fetchall()
    
    total_due_this_month = conn.execute('''
        SELECT SUM(amount - paid_amount) as total FROM contract_payments
        WHERE status IN ('مستحقة', 'مدفوعة جزئيا')
        AND strftime('%Y-%m', due_date) = ?
    ''', (current_month,)).fetchone()['total'] or 0
    
    # المهام المتأخرة
    overdue_list = conn.execute('''
        SELECT tasks.*, clients.name as client_name, users.name as assigned_name 
        FROM tasks 
        JOIN clients ON tasks.client_id = clients.id 
        JOIN users ON tasks.assigned_to = users.id 
        WHERE due_date < date("now") AND status != "مكتملة"
        ORDER BY due_date ASC LIMIT 10
    ''').fetchall()
    
    recent_activity = conn.execute('''
        SELECT activity_log.*, users.name as user_name 
        FROM activity_log 
        JOIN users ON activity_log.user_id = users.id 
        ORDER BY activity_log.created_at DESC LIMIT 10
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
                         total_payments=total_payments,
                         total_contracts=total_contracts,
                         contracts_paid_full=contracts_paid_full,
                         contracts_partial=contracts_partial,
                         contracts_unpaid=contracts_unpaid,
                         contracts_unpaid_amount=contracts_unpaid_amount,
                         contracts_paid_percent=contracts_paid_percent,
                         contracts_partial_due=contracts_partial_due,
                         recent_contracts=recent_contracts,
                         due_this_month=due_this_month,
                         overdue_payments=overdue_payments,
                         total_due_this_month=total_due_this_month,
                         current_month=current_month,
                         overdue_list=overdue_list,
                         recent_activity=recent_activity,
                         settings=settings)
# ============================================================
# ===== المدربين - مسارات مباشرة =====
# ============================================================

@app.route('/trainers')
def trainers_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    trainers = conn.execute('''
        SELECT t.*, COUNT(ct.client_id) as client_count 
        FROM trainers t
        LEFT JOIN client_trainers ct ON t.id = ct.trainer_id
        GROUP BY t.id
        ORDER BY t.name
    ''').fetchall()
    conn.close()
    
    for trainer in trainers:
        if trainer['client_count'] is None:
            trainer['client_count'] = 0
    
    return render_template('trainers.html', trainers=trainers)


@app.route('/trainer/<int:trainer_id>')
def trainer_details_page(trainer_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    trainer = conn.execute('SELECT * FROM trainers WHERE id = ?', (trainer_id,)).fetchone()
    
    if not trainer:
        conn.close()
        return "المدرب غير موجود", 404
    
    clients = conn.execute('''
        SELECT c.* 
        FROM clients c
        JOIN client_trainers ct ON c.id = ct.client_id
        WHERE ct.trainer_id = ?
        ORDER BY c.name
    ''', (trainer_id,)).fetchall()
    conn.close()
    
    return render_template('trainer_details.html', trainer=trainer, clients=clients)


@app.route('/add_trainer', methods=['GET', 'POST'])
def add_trainer_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        specialty = request.form.get('specialty')
        notes = request.form.get('notes')
        is_active = 1 if request.form.get('is_active') else 0
        
        if not name:
            flash('اسم المدرب مطلوب', 'error')
            return render_template('add_trainer.html')
        
        conn = get_db()
        conn.execute('''
            INSERT INTO trainers (name, phone, email, specialty, notes, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, phone, email, specialty, notes, is_active))
        conn.commit()
        conn.close()
        
        flash('تم إضافة المدرب بنجاح', 'success')
        return redirect(url_for('trainers_page'))
    
    return render_template('add_trainer.html')


@app.route('/edit_trainer/<int:trainer_id>', methods=['GET', 'POST'])
def edit_trainer_page(trainer_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    trainer = conn.execute('SELECT * FROM trainers WHERE id = ?', (trainer_id,)).fetchone()
    
    if not trainer:
        conn.close()
        return "المدرب غير موجود", 404
    
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        specialty = request.form.get('specialty')
        notes = request.form.get('notes')
        is_active = 1 if request.form.get('is_active') else 0
        
        if not name:
            flash('اسم المدرب مطلوب', 'error')
            return render_template('edit_trainer.html', trainer=trainer)
        
        conn.execute('''
            UPDATE trainers 
            SET name = ?, phone = ?, email = ?, specialty = ?, notes = ?, is_active = ?
            WHERE id = ?
        ''', (name, phone, email, specialty, notes, is_active, trainer_id))
        conn.commit()
        conn.close()
        
        flash('تم تحديث المدرب بنجاح', 'success')
        return redirect(url_for('trainer_details_page', trainer_id=trainer_id))
    
    conn.close()
    return render_template('edit_trainer.html', trainer=trainer)


@app.route('/delete_trainer/<int:trainer_id>', methods=['POST'])
def delete_trainer_page(trainer_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    clients = conn.execute('SELECT COUNT(*) as count FROM client_trainers WHERE trainer_id = ?', (trainer_id,)).fetchone()
    
    if clients['count'] > 0:
        flash('لا يمكن حذف المدرب لأنه مرتبط بعملاء', 'error')
        conn.close()
        return redirect(url_for('trainer_details_page', trainer_id=trainer_id))
    
    conn.execute('DELETE FROM trainers WHERE id = ?', (trainer_id,))
    conn.commit()
    conn.close()
    
    flash('تم حذف المدرب بنجاح', 'success')
    return redirect(url_for('trainers_page'))                        


# ===== البحث الشامل =====
@app.route('/global_search')
def global_search():
    """بحث شامل في جميع الجداول"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    query = request.args.get('q', '').strip()
    if not query:
        flash('❌ يرجى إدخال كلمة بحث', 'warning')
        return redirect(url_for('index'))
    
    conn = get_db()
    results = {
        'clients': [],
        'contracts': [],
        'payments': [],
        'tasks': [],
        'trainers': []
    }
    
    search_term = f'%{query}%'
    
    # ===== البحث في العملاء =====
    clients = conn.execute('''
        SELECT id, name, company_name, phone, email, 'client' as type
        FROM clients
        WHERE name LIKE ? OR company_name LIKE ? OR phone LIKE ? OR email LIKE ?
        LIMIT 20
    ''', (search_term, search_term, search_term, search_term)).fetchall()
    results['clients'] = clients
    
    # ===== البحث في العقود =====
    contracts = conn.execute('''
        SELECT client_contracts.id, client_contracts.contract_number, client_contracts.title,
               clients.name as client_name, clients.company_name,
               'contract' as type
        FROM client_contracts
        JOIN clients ON client_contracts.client_id = clients.id
        WHERE client_contracts.contract_number LIKE ? 
           OR client_contracts.title LIKE ?
           OR clients.name LIKE ?
           OR clients.company_name LIKE ?
        LIMIT 20
    ''', (search_term, search_term, search_term, search_term)).fetchall()
    results['contracts'] = contracts
    
    # ===== البحث في المدفوعات =====
    payments = conn.execute('''
        SELECT client_payments.id, client_payments.amount, client_payments.payment_date,
               clients.name as client_name, clients.company_name,
               'payment' as type
        FROM client_payments
        JOIN clients ON client_payments.client_id = clients.id
        WHERE clients.name LIKE ? 
           OR clients.company_name LIKE ?
           OR client_payments.invoice_number LIKE ?
        LIMIT 20
    ''', (search_term, search_term, search_term)).fetchall()
    results['payments'] = payments
    
    # ===== البحث في التدريبات =====
    tasks = conn.execute('''
        SELECT tasks.id, tasks.title, tasks.status, tasks.due_date,
               clients.name as client_name, clients.company_name,
               trainers.name as trainer_name,
               'task' as type
        FROM tasks
        JOIN clients ON tasks.client_id = clients.id
        LEFT JOIN trainers ON tasks.assigned_to = trainers.id
        WHERE clients.name LIKE ? 
           OR clients.company_name LIKE ?
           OR tasks.title LIKE ?
           OR trainers.name LIKE ?
        LIMIT 20
    ''', (search_term, search_term, search_term, search_term)).fetchall()
    results['tasks'] = tasks
    
    # ===== البحث في المدربين =====
    trainers = conn.execute('''
        SELECT id, name, phone, email, specialty, 'trainer' as type
        FROM trainers
        WHERE name LIKE ? OR phone LIKE ? OR email LIKE ? OR specialty LIKE ?
        LIMIT 20
    ''', (search_term, search_term, search_term, search_term)).fetchall()
    results['trainers'] = trainers
    
    conn.close()
    
    total_results = sum(len(v) for v in results.values())
    
    return render_template('global_search.html', 
                         results=results, 
                         query=query,
                         total_results=total_results)


# ===== Health Check =====
@app.route('/health')
def health():
    return jsonify({"status": "ok", "message": "Application is running"}), 200


# ===== معالج الأخطاء =====
@app.errorhandler(404)
def page_not_found(e):
    settings = get_company_settings()
    return render_template('404.html', settings=settings), 404


@app.errorhandler(500)
def internal_server_error(e):
    flash('❌ حدث خطأ في السيرفر. يرجى المحاولة مرة أخرى.', 'danger')
    return redirect(url_for('index'))


# ===== Debug: عرض كل المسارات المسجلة =====
@app.route('/show-routes')
def show_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(f"{rule.endpoint}: {rule.rule}")
    return "<br>".join(sorted(routes))


# ===== مسار اختبار =====
@app.route('/test')
def test():
    return "✅ التطبيق شغال!"


# ===== تشغيل التطبيق =====
if __name__ == '__main__':
    print("🚀 جاري تشغيل السيرفر...")
    print("📍 افتح المتصفح على: http://127.0.0.1:5000")
    print("👤 حسابات تجريبية:")
    print("   Adminerp / 1234 (مدير)")
    print("   Fahd01 / 1234 (مدير)")
    print("   employee1 / 1234 (موظف)")
    print("   viewer1 / 1234 (مراقب)")
    app.run(debug=True, host='0.0.0.0', port=5000)