# app.py
import os
from flask import Flask, render_template, redirect, url_for, session, flash, jsonify, request, Blueprint
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

# ===== تعريف Blueprints =====
auth_bp = Blueprint('auth', __name__, url_prefix='/')
users_bp = Blueprint('users', __name__, url_prefix='/')
clients_bp = Blueprint('clients', __name__, url_prefix='/')
trainers_bp = Blueprint('trainers', __name__, url_prefix='/trainers')
tasks_bp = Blueprint('tasks', __name__, url_prefix='/')
contracts_bp = Blueprint('contracts', __name__, url_prefix='/')
payments_bp = Blueprint('payments', __name__, url_prefix='/')
modules_bp = Blueprint('modules', __name__, url_prefix='/')
meetings_bp = Blueprint('meetings', __name__, url_prefix='/')
reports_bp = Blueprint('reports', __name__, url_prefix='/')
settings_bp = Blueprint('settings', __name__, url_prefix='/')
backups_bp = Blueprint('backups', __name__, url_prefix='/')

# ===== استيراد الـ Routes =====
from routes import auth, users, clients, trainers, tasks, contracts, payments, modules, meetings, reports, settings, backups

# ===== تسجيل Blueprints =====
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
