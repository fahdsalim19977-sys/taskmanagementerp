# routes/clients.py
from flask import render_template, request, redirect, url_for, session, flash
from models import get_db
from routes import clients_bp
from utils import get_trainers, check_role, log_activity, get_company_settings
from datetime import datetime
import math

@clients_bp.route('/clients')
def clients():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # ===== خيارات العرض والترقيم =====
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '').strip()
    
    if per_page == 0 or per_page == 999999:
        per_page = 999999
        page = 1
    
    conn = get_db()
    
    # ===== بناء الاستعلام =====
    query = '''
        SELECT clients.*, 
               GROUP_CONCAT(trainers.name, ', ') as trainer_names
        FROM clients
        LEFT JOIN client_trainers ON clients.id = client_trainers.client_id
        LEFT JOIN trainers ON client_trainers.trainer_id = trainers.id
        WHERE 1=1
    '''
    params = []
    
    if search:
        query += ' AND (clients.name LIKE ? OR clients.company_name LIKE ? OR clients.phone LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param])
    
    query += ' GROUP BY clients.id ORDER BY clients.name'
    
    # ===== إجمالي النتائج =====
    count_query = '''
        SELECT COUNT(DISTINCT clients.id) as count
        FROM clients
        LEFT JOIN client_trainers ON clients.id = client_trainers.client_id
        LEFT JOIN trainers ON client_trainers.trainer_id = trainers.id
        WHERE 1=1
    '''
    count_params = []
    if search:
        count_query += ' AND (clients.name LIKE ? OR clients.company_name LIKE ? OR clients.phone LIKE ?)'
        count_params.extend([search_param, search_param, search_param])
    
    total = conn.execute(count_query, count_params).fetchone()['count']
    
    # ===== ترقيم =====
    if per_page != 999999:
        query += ' LIMIT ? OFFSET ?'
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
    
    clients_list = conn.execute(query, params).fetchall()
    conn.close()
    
    total_pages = math.ceil(total / per_page) if per_page != 999999 and total > 0 else 1
    per_page_options = [10, 25, 50, 100]
    
    return render_template('clients.html', 
                         clients=clients_list,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         per_page=per_page,
                         per_page_options=per_page_options,
                         search=search)


@clients_bp.route('/add_client', methods=['GET', 'POST'])
def add_client():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
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
                conn.execute('INSERT INTO client_trainers (client_id, trainer_id) VALUES (?, ?)', 
                           (client_id, trainer_id))
        
        conn.commit()
        conn.close()
        
        flash('✅ تم إضافة العميل بنجاح', 'success')
        log_activity(session['user_id'], 'إضافة عميل', f'أضاف {name}')
        return redirect(url_for('clients.clients'))
    
    return render_template('add_client.html', trainers=trainers)


@clients_bp.route('/edit_client/<int:client_id>', methods=['GET', 'POST'])
def edit_client(client_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('❌ العميل غير موجود', 'danger')
        conn.close()
        return redirect(url_for('clients.clients'))
    
    current_trainers = conn.execute('SELECT trainer_id FROM client_trainers WHERE client_id = ?', 
                                  (client_id,)).fetchall()
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
            UPDATE clients SET name = ?, phone = ?, email = ?, address = ?, 
            company_name = ?, notes = ? WHERE id = ?
        ''', (name, phone, email, address, company_name, notes, client_id))
        
        conn.execute('DELETE FROM client_trainers WHERE client_id = ?', (client_id,))
        for trainer_id in trainer_ids:
            if trainer_id:
                conn.execute('INSERT INTO client_trainers (client_id, trainer_id) VALUES (?, ?)', 
                           (client_id, trainer_id))
        
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث العميل بنجاح', 'success')
        log_activity(session['user_id'], 'تحديث عميل', f'حدث {name}')
        return redirect(url_for('clients.clients'))
    
    conn.close()
    return render_template('edit_client.html', client=client, trainers=trainers, 
                         current_trainer_ids=current_trainer_ids)


@clients_bp.route('/delete_client/<int:client_id>', methods=['POST'])
def delete_client(client_id):
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('clients.clients'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('❌ العميل غير موجود', 'danger')
        conn.close()
        return redirect(url_for('clients.clients'))
    
    conn.execute('DELETE FROM clients WHERE id = ?', (client_id,))
    conn.execute('DELETE FROM client_trainers WHERE client_id = ?', (client_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف العميل بنجاح', 'success')
    log_activity(session['user_id'], 'حذف عميل', f'حذف عميل رقم {client_id}')
    return redirect(url_for('clients.clients'))


# ===== مهام العميل =====
@clients_bp.route('/client_tasks/<int:client_id>')
def client_tasks(client_id):
    """عرض مهام عميل معين"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    # جلب بيانات العميل
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        conn.close()
        flash('❌ العميل غير موجود', 'danger')
        return redirect(url_for('clients.clients'))
    
    # جلب مهام العميل
    tasks = conn.execute('''
        SELECT tasks.*, trainers.name as assigned_name
        FROM tasks
        LEFT JOIN trainers ON tasks.assigned_to = trainers.id
        WHERE tasks.client_id = ?
        ORDER BY tasks.due_date ASC
    ''', (client_id,)).fetchall()
    conn.close()
    
    # إحصائيات المهام
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


# ===== طباعة مهام العميل =====
@clients_bp.route('/print_client_tasks/<int:client_id>')
def print_client_tasks(client_id):
    """طباعة مهام عميل معين"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    # جلب بيانات العميل
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        conn.close()
        flash('❌ العميل غير موجود', 'danger')
        return redirect(url_for('clients.clients'))
    
    # جلب مهام العميل مع اسم المدرب
    tasks = conn.execute('''
        SELECT tasks.*, trainers.name as assigned_name
        FROM tasks
        LEFT JOIN trainers ON tasks.assigned_to = trainers.id
        WHERE tasks.client_id = ?
        ORDER BY tasks.due_date ASC
    ''', (client_id,)).fetchall()
    conn.close()
    
    # تصنيف المهام حسب الحالة
    completed_tasks = [t for t in tasks if t['status'] == 'مكتملة']
    in_progress_tasks = [t for t in tasks if t['status'] == 'قيد التنفيذ']
    overdue_tasks = [t for t in tasks if t['status'] == 'متأخرة']
    not_started_tasks = [t for t in tasks if t['status'] == 'لم تبدأ']
    
    # إعدادات الشركة
    settings = get_company_settings()
    
    return render_template('print_client_tasks.html',
                         client=client,
                         tasks=tasks,
                         completed_tasks=completed_tasks,
                         in_progress_tasks=in_progress_tasks,
                         overdue_tasks=overdue_tasks,
                         not_started_tasks=not_started_tasks,
                         settings=settings,
                         today=datetime.now().date())


# ===== مدفوعات العميل =====
@clients_bp.route('/client_payments/<int:client_id>')
def client_payments(client_id):
    """عرض مدفوعات عميل معين"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    # جلب بيانات العميل
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        conn.close()
        flash('❌ العميل غير موجود', 'danger')
        return redirect(url_for('clients.clients'))
    
    # جلب مدفوعات العميل
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
    
    # إحصائيات المدفوعات
    stats = {
        'total_count': len(payments),
        'total_paid': sum(p['amount'] for p in payments if p['status'] == 'مدفوع'),
        'total_pending': sum(p['amount'] for p in payments if p['status'] == 'معلق'),
        'total_overdue': sum(p['amount'] for p in payments if p['status'] == 'متأخر')
    }
    conn.close()
    
    return render_template('client_payments.html',
                         client=client,
                         payments=payments,
                         stats=stats)


# ===== تقرير شامل للعميل =====
@clients_bp.route('/print_client_full_report/<int:client_id>')
def print_client_full_report(client_id):
    """تقرير شامل للعميل (مدفوعات + مهام + مديولات)"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    # جلب بيانات العميل
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        conn.close()
        flash('❌ العميل غير موجود', 'danger')
        return redirect(url_for('clients.clients'))
    
    # جلب المدفوعات
    payments = conn.execute('''
        SELECT client_payments.*, 
               client_modules.name as module_name
        FROM client_payments
        LEFT JOIN client_modules ON client_payments.module_id = client_modules.id
        WHERE client_payments.client_id = ?
        ORDER BY client_payments.created_at DESC
    ''', (client_id,)).fetchall()
    
    # إحصائيات المدفوعات
    stats = {
        'total_count': len(payments),
        'total_paid': sum(p['amount'] for p in payments if p['status'] == 'مدفوع'),
        'total_pending': sum(p['amount'] for p in payments if p['status'] == 'معلق'),
        'total_overdue': sum(p['amount'] for p in payments if p['status'] == 'متأخر')
    }
    
    # جلب المديولات
    modules = conn.execute('''
        SELECT * FROM client_modules 
        WHERE client_id = ? 
        ORDER BY created_at DESC
    ''', (client_id,)).fetchall()
    
    # جلب دفعات العقود
    contract_payments = conn.execute('''
        SELECT contract_payments.*, 
               client_contracts.contract_number
        FROM contract_payments
        JOIN client_contracts ON contract_payments.contract_id = client_contracts.id
        WHERE client_contracts.client_id = ?
        ORDER BY contract_payments.installment_number ASC
    ''', (client_id,)).fetchall()
    
    # إحصائيات دفعات العقود
    contract_stats = {
        'total_paid': sum(p['paid_amount'] or 0 for p in contract_payments if p['status'] == 'مدفوعة'),
        'total_due': sum(p['amount'] for p in contract_payments if p['status'] == 'مستحقة'),
        'total_overdue': sum(p['amount'] for p in contract_payments if p['status'] == 'متأخرة')
    }
    
    settings = get_company_settings()
    conn.close()
    
    return render_template('print_client_full_report.html',
                         client=client,
                         payments=payments,
                         stats=stats,
                         modules=modules,
                         contract_payments=contract_payments,
                         contract_stats=contract_stats,
                         settings=settings,
                         today=datetime.now().date())