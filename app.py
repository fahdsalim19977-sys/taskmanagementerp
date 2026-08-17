# app.py
import os
import math
from flask import Flask, render_template, redirect, url_for, session, flash, jsonify, request
from config import Config
from models import init_db, get_db
from utils import get_company_settings, get_lang, t, log_activity
from datetime import datetime
from routes import trainers_bp

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

# ============================================================
# ===== الصفحة الرئيسية =====
# ============================================================
# ============================================================
# ===== الصفحة الرئيسية / Dashboard =====
# ============================================================

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    # ===== إحصائيات سريعة =====
    stats = {
        'clients': conn.execute('SELECT COUNT(*) as count FROM clients').fetchone()['count'],
        'trainers': conn.execute('SELECT COUNT(*) as count FROM trainers').fetchone()['count'],
        'tasks': conn.execute('SELECT COUNT(*) as count FROM tasks').fetchone()['count'],
        'contracts': conn.execute('SELECT COUNT(*) as count FROM client_contracts').fetchone()['count'],
        'payments': conn.execute('SELECT COUNT(*) as count FROM client_payments').fetchone()['count'],
        'meetings': conn.execute('SELECT COUNT(*) as count FROM meetings').fetchone()['count'],
        'users': conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count'],
        'modules': conn.execute('SELECT COUNT(*) as count FROM client_modules').fetchone()['count']
    }
    
    # ===== المهام حسب الحالة =====
    tasks_by_status = {
        'completed': conn.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "مكتملة"').fetchone()['count'],
        'in_progress': conn.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "قيد التنفيذ"').fetchone()['count'],
        'overdue': conn.execute('SELECT COUNT(*) as count FROM tasks WHERE due_date < date("now") AND status != "مكتملة"').fetchone()['count'],
        'not_started': conn.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "لم تبدأ"').fetchone()['count']
    }
    
    # ===== العقود حسب الحالة =====
    contracts_by_status = {
        'active': conn.execute('SELECT COUNT(*) as count FROM client_contracts WHERE status = "نشط"').fetchone()['count'],
        'pending': conn.execute('SELECT COUNT(*) as count FROM client_contracts WHERE status = "معلق"').fetchone()['count'],
        'completed': conn.execute('SELECT COUNT(*) as count FROM client_contracts WHERE status = "منتهي"').fetchone()['count']
    }
    
    # ===== المدفوعات =====
    payments_stats = {
        'total': conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع"').fetchone()['total'] or 0,
        'pending': conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "معلق"').fetchone()['total'] or 0,
        'overdue': conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "متأخر"').fetchone()['total'] or 0
    }
    
    # ===== آخر 5 عقود =====
    recent_contracts = conn.execute('''
        SELECT client_contracts.*, clients.name as client_name
        FROM client_contracts
        JOIN clients ON client_contracts.client_id = clients.id
        ORDER BY client_contracts.created_at DESC LIMIT 5
    ''').fetchall()
    
    # ===== آخر 5 مهام =====
    recent_tasks = conn.execute('''
    SELECT tasks.*, clients.name as client_name, 
           trainers.name as trainer_name,
           users.name as assigned_user_name
    FROM tasks
    JOIN clients ON tasks.client_id = clients.id
    LEFT JOIN trainers ON tasks.trainer_id = trainers.id
    LEFT JOIN users ON tasks.assigned_user_id = users.id
    ORDER BY tasks.created_at DESC LIMIT 5
''').fetchall()
    
    # ===== آخر 5 أنشطة =====
    recent_activities = conn.execute('''
        SELECT activity_log.*, users.name as user_name
        FROM activity_log
        JOIN users ON activity_log.user_id = users.id
        ORDER BY activity_log.created_at DESC LIMIT 5
    ''').fetchall()
    
    # ===== توزيع العملاء حسب المدربين =====
    trainer_distribution = conn.execute('''
        SELECT trainers.name, COUNT(client_trainers.client_id) as count
        FROM trainers
        LEFT JOIN client_trainers ON trainers.id = client_trainers.trainer_id
        GROUP BY trainers.id
        ORDER BY count DESC
        LIMIT 5
    ''').fetchall()
    
    conn.close()
    settings = get_company_settings()
    
    return render_template('dashboard.html',
                         stats=stats,
                         tasks_by_status=tasks_by_status,
                         contracts_by_status=contracts_by_status,
                         payments_stats=payments_stats,
                         recent_contracts=recent_contracts,
                         recent_tasks=recent_tasks,
                         recent_activities=recent_activities,
                         trainer_distribution=trainer_distribution,
                         settings=settings,
                         datetime=datetime)

# ============================================================
# ===== المدربين - مسارات مباشرة =====
# ============================================================

@app.route('/trainers')
def trainers_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '').strip()
    
    if per_page == 0 or per_page == 999999:
        per_page = 999999
        page = 1
    
    conn = get_db()
    
    query = '''
        SELECT t.*, COUNT(ct.client_id) as client_count 
        FROM trainers t
        LEFT JOIN client_trainers ct ON t.id = ct.trainer_id
        WHERE 1=1
    '''
    params = []
    
    if search:
        query += ' AND (t.name LIKE ? OR t.phone LIKE ? OR t.email LIKE ? OR t.specialty LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param, search_param])
    
    query += ' GROUP BY t.id ORDER BY t.name'
    
    count_query = '''
        SELECT COUNT(DISTINCT t.id) as count
        FROM trainers t
        LEFT JOIN client_trainers ct ON t.id = ct.trainer_id
        WHERE 1=1
    '''
    count_params = []
    if search:
        count_query += ' AND (t.name LIKE ? OR t.phone LIKE ? OR t.email LIKE ? OR t.specialty LIKE ?)'
        count_params.extend([search_param, search_param, search_param, search_param])
    
    total = conn.execute(count_query, count_params).fetchone()['count']
    
    if per_page != 999999:
        query += ' LIMIT ? OFFSET ?'
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
    
    trainers = conn.execute(query, params).fetchall()
    conn.close()
    
    for trainer in trainers:
        if trainer['client_count'] is None:
            trainer['client_count'] = 0
    
    total_pages = math.ceil(total / per_page) if per_page != 999999 and total > 0 else 1
    per_page_options = [10, 25, 50, 100]
    
    return render_template('trainers.html', 
                         trainers=trainers,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         per_page=per_page,
                         per_page_options=per_page_options,
                         search=search)


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


# ============================================================
# ===== مهام العميل - مسار مباشر =====
# ============================================================

@app.route('/client_tasks/<int:client_id>')
def client_tasks_page(client_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        conn.close()
        flash('❌ العميل غير موجود', 'danger')
        return redirect(url_for('clients.clients'))
    
    tasks = conn.execute('''
        SELECT tasks.*, trainers.name as assigned_name
        FROM tasks
        LEFT JOIN trainers ON tasks.assigned_to = trainers.id
        WHERE tasks.client_id = ?
        ORDER BY tasks.due_date ASC
    ''', (client_id,)).fetchall()
    conn.close()
    
    stats = {
        'total': len(tasks),
        'completed': len([t for t in tasks if t['status'] == 'مكتملة']),
        'in_progress': len([t for t in tasks if t['status'] == 'قيد التنفيذ']),
        'overdue': len([t for t in tasks if t['status'] == 'متأخرة']),
        'not_started': len([t for t in tasks if t['status'] == 'لم تبدأ'])
    }
    
    return render_template('client_tasks.html', 
                         client=client, 
                         tasks=tasks, 
                         stats=stats,
                         today=datetime.now().date())


# ============================================================
# ===== أنواع العقود والموديولات - مسارات مباشرة =====
# ============================================================

@app.route('/contract_types')
def contract_types_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    types = conn.execute('SELECT * FROM contract_types ORDER BY name').fetchall()
    conn.close()
    return render_template('contract_types.html', types=types)


@app.route('/add_contract_type', methods=['POST'])
def add_contract_type():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '')
    
    if not name:
        flash('❌ اسم نوع العقد مطلوب', 'danger')
        return redirect(url_for('contract_types_page'))
    
    conn = get_db()
    conn.execute('''
        INSERT INTO contract_types (name, description)
        VALUES (?, ?)
    ''', (name, description))
    conn.commit()
    conn.close()
    
    flash('✅ تم إضافة نوع العقد بنجاح', 'success')
    return redirect(url_for('contract_types_page'))


@app.route('/edit_contract_type/<int:type_id>', methods=['POST'])
def edit_contract_type(type_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '')
    is_active = 1 if request.form.get('is_active') else 0
    
    if not name:
        flash('❌ اسم نوع العقد مطلوب', 'danger')
        return redirect(url_for('contract_types_page'))
    
    conn = get_db()
    conn.execute('''
        UPDATE contract_types 
        SET name = ?, description = ?, is_active = ?
        WHERE id = ?
    ''', (name, description, is_active, type_id))
    conn.commit()
    conn.close()
    
    flash('✅ تم تحديث نوع العقد بنجاح', 'success')
    return redirect(url_for('contract_types_page'))


@app.route('/delete_contract_type/<int:type_id>', methods=['POST'])
def delete_contract_type(type_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    conn.execute('DELETE FROM contract_types WHERE id = ?', (type_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف نوع العقد بنجاح', 'success')
    return redirect(url_for('contract_types_page'))


@app.route('/module_types')
def module_types_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    types = conn.execute('SELECT * FROM module_types ORDER BY name').fetchall()
    conn.close()
    return render_template('module_types.html', types=types)


@app.route('/add_module_type', methods=['POST'])
def add_module_type():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '')
    price = request.form.get('price', 0)
    
    if not name:
        flash('❌ اسم المديول مطلوب', 'danger')
        return redirect(url_for('module_types_page'))
    
    conn = get_db()
    conn.execute('''
        INSERT INTO module_types (name, description, price)
        VALUES (?, ?, ?)
    ''', (name, description, price))
    conn.commit()
    conn.close()
    
    flash('✅ تم إضافة نوع المديول بنجاح', 'success')
    return redirect(url_for('module_types_page'))


@app.route('/edit_module_type/<int:type_id>', methods=['POST'])
def edit_module_type(type_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '')
    price = request.form.get('price', 0)
    is_active = 1 if request.form.get('is_active') else 0
    
    if not name:
        flash('❌ اسم المديول مطلوب', 'danger')
        return redirect(url_for('module_types_page'))
    
    conn = get_db()
    conn.execute('''
        UPDATE module_types 
        SET name = ?, description = ?, price = ?, is_active = ?
        WHERE id = ?
    ''', (name, description, price, is_active, type_id))
    conn.commit()
    conn.close()
    
    flash('✅ تم تحديث نوع المديول بنجاح', 'success')
    return redirect(url_for('module_types_page'))


@app.route('/delete_module_type/<int:type_id>', methods=['POST'])
def delete_module_type(type_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    conn.execute('DELETE FROM module_types WHERE id = ?', (type_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف نوع المديول بنجاح', 'success')
    return redirect(url_for('module_types_page'))


# ============================================================
# ===== البحث الشامل =====
# ============================================================

@app.route('/global_search')
def global_search():
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
    
    clients = conn.execute('''
        SELECT id, name, company_name, phone, email, 'client' as type
        FROM clients
        WHERE name LIKE ? OR company_name LIKE ? OR phone LIKE ? OR email LIKE ?
        LIMIT 20
    ''', (search_term, search_term, search_term, search_term)).fetchall()
    results['clients'] = clients
    
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


# ============================================================
# ===== Health Check =====
# ============================================================

@app.route('/health')
def health():
    return jsonify({"status": "ok", "message": "Application is running"}), 200


# ============================================================
# ===== معالج الأخطاء =====
# ============================================================

@app.errorhandler(404)
def page_not_found(e):
    settings = get_company_settings()
    return render_template('404.html', settings=settings), 404


@app.errorhandler(500)
def internal_server_error(e):
    flash('❌ حدث خطأ في السيرفر. يرجى المحاولة مرة أخرى.', 'danger')
    return redirect(url_for('index'))


# ============================================================
# ===== مسارات اختبار =====
# ============================================================

@app.route('/trainers-test')
def trainers_test():
    return "Trainers route is working! (test)"


@app.route('/trainers-direct')
def trainers_direct():
    from routes.trainers import trainers_bp
    return "Direct import test"


# ============================================================
# ===== تشغيل التطبيق =====
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