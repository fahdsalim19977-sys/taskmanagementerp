# routes/tasks.py
from flask import render_template, request, redirect, url_for, session, flash, send_file, current_app
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os
from models import get_db
from routes import tasks_bp
from utils import log_activity, check_role

@tasks_bp.route('/tasks')
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    user_role = session['user_role']
    
    if user_role == 'موظف':
        task_list = conn.execute('''
            SELECT tasks.*, clients.name as client_name, clients.company_name, trainers.name as assigned_name 
            FROM tasks 
            JOIN clients ON tasks.client_id = clients.id 
            JOIN trainers ON tasks.assigned_to = trainers.id 
            WHERE tasks.assigned_to = ?
            ORDER BY tasks.due_date ASC
        ''', (session['user_id'],)).fetchall()
    else:
        task_list = conn.execute('''
            SELECT tasks.*, clients.name as client_name, clients.company_name, trainers.name as assigned_name 
            FROM tasks 
            JOIN clients ON tasks.client_id = clients.id 
            JOIN trainers ON tasks.assigned_to = trainers.id 
            ORDER BY tasks.due_date ASC
        ''').fetchall()
    
    conn.close()
    return render_template('tasks.html', tasks=task_list, today=datetime.now().date())


@tasks_bp.route('/add_task', methods=['GET', 'POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    if session['user_role'] == 'مراقب':
        flash('⛔ ليس لديك صلاحية لإضافة مهام', 'danger')
        return redirect(url_for('tasks.tasks'))
    
    conn = get_db()
    clients = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
    trainers = conn.execute('SELECT id, name FROM trainers WHERE is_active = 1 ORDER BY name').fetchall()
    meetings = conn.execute('SELECT id, title, client_id FROM meetings WHERE date(meeting_date) >= date("now") AND status = "مجدول" ORDER BY meeting_date ASC').fetchall()
    
    # ✅ جلب جميع الدفعات
    available_payments = conn.execute('''
        SELECT contract_payments.*, 
               client_contracts.contract_number,
               client_contracts.client_id
        FROM contract_payments
        JOIN client_contracts ON contract_payments.contract_id = client_contracts.id
        ORDER BY client_contracts.client_id, contract_payments.due_date
    ''').fetchall()
    conn.close()
    
    if request.method == 'POST':
        client_id = request.form['client_id']
        assigned_to = request.form['assigned_to']
        title = request.form['title']
        description = request.form.get('description', '')
        due_date = request.form['due_date']
        priority = request.form['priority']
        estimated_duration = request.form.get('estimated_duration', 0)
        meeting_id = request.form.get('meeting_id') or None
        task_group = request.form.get('task_group', '')
        contract_payment_id = request.form.get('contract_payment_id') or None
        
        print(f"📝 إضافة تدريب جديد: {title}")
        print(f"   مرتبط بدفعة: {contract_payment_id}")
        
        conn = get_db()
        cursor = conn.execute('''
            INSERT INTO tasks (client_id, assigned_to, title, description, due_date, priority, 
                             estimated_duration, meeting_id, task_group, contract_payment_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, assigned_to, title, description, due_date, priority, 
              estimated_duration, meeting_id, task_group, contract_payment_id))
        task_id = cursor.lastrowid
        conn.commit()
        
        message = f'📋 تم تكليفك بمهمة جديدة: {title}'
        conn.execute('INSERT INTO notifications (user_id, task_id, message) VALUES (?, ?, ?)', 
                    (assigned_to, task_id, message))
        conn.commit()
        conn.close()
        
        flash('✅ تم إضافة التدريب بنجاح', 'success')
        log_activity(session['user_id'], 'إضافة تدريب', f'أضاف {title}')
        return redirect(url_for('tasks.tasks'))
    
    return render_template('add_task.html', 
                         clients=clients, 
                         trainers=trainers, 
                         meetings=meetings,
                         available_payments=available_payments)


@tasks_bp.route('/task/<int:task_id>')
def task_details(task_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    task = conn.execute('''
        SELECT tasks.*, 
               clients.name as client_name, 
               clients.phone as client_phone,
               clients.email as client_email,
               clients.address as client_address,
               clients.company_name as client_company,
               trainers.name as assigned_name,
               trainers.email as assigned_email
        FROM tasks 
        JOIN clients ON tasks.client_id = clients.id 
        JOIN trainers ON tasks.assigned_to = trainers.id 
        WHERE tasks.id = ?
    ''', (task_id,)).fetchone()
    
    if not task:
        flash('❌ التدريب غير موجود', 'danger')
        conn.close()
        return redirect(url_for('tasks.tasks'))
    
    updates = conn.execute('''
        SELECT task_updates.*, users.name as user_name
        FROM task_updates
        JOIN users ON task_updates.user_id = users.id
        WHERE task_updates.task_id = ?
        ORDER BY task_updates.created_at DESC
    ''', (task_id,)).fetchall()
    conn.close()
    return render_template('task_details.html', task=task, updates=updates, today=datetime.now().date())


@tasks_bp.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    task = conn.execute('''
        SELECT tasks.*, clients.name as client_name 
        FROM tasks 
        JOIN clients ON tasks.client_id = clients.id 
        WHERE tasks.id = ?
    ''', (task_id,)).fetchone()
    
    if not task:
        flash('❌ التدريب غير موجود', 'danger')
        conn.close()
        return redirect(url_for('tasks.tasks'))
    
    user_role = session['user_role']
    if user_role == 'مراقب':
        flash('⛔ ليس لديك صلاحية لتعديل التدريبات', 'danger')
        conn.close()
        return redirect(url_for('tasks.tasks'))
    if user_role == 'موظف' and task['assigned_to'] != session['user_id']:
        flash('⛔ يمكنك تعديل تدريباتك فقط', 'danger')
        conn.close()
        return redirect(url_for('tasks.tasks'))
    
    clients = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
    trainers = conn.execute('SELECT id, name FROM trainers WHERE is_active = 1 ORDER BY name').fetchall()
    
    # ✅ جلب جميع الدفعات
    available_payments = conn.execute('''
        SELECT contract_payments.*, 
               client_contracts.contract_number,
               client_contracts.client_id
        FROM contract_payments
        JOIN client_contracts ON contract_payments.contract_id = client_contracts.id
        ORDER BY client_contracts.client_id, contract_payments.due_date
    ''').fetchall()
    
    if request.method == 'POST':
        client_id = request.form['client_id']
        assigned_to = request.form['assigned_to']
        title = request.form['title']
        description = request.form.get('description', '')
        due_date = request.form['due_date']
        priority = request.form['priority']
        estimated_duration = request.form.get('estimated_duration', 0)
        task_group = request.form.get('task_group', '')
        contract_payment_id = request.form.get('contract_payment_id') or None
        
        conn.execute('''
            UPDATE tasks SET 
                client_id = ?,
                assigned_to = ?,
                title = ?,
                description = ?,
                due_date = ?,
                priority = ?,
                estimated_duration = ?,
                task_group = ?,
                contract_payment_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (client_id, assigned_to, title, description, due_date, priority, 
              estimated_duration, task_group, contract_payment_id, task_id))
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث التدريب بنجاح', 'success')
        log_activity(session['user_id'], 'تعديل تدريب', f'عدل {title}')
        return redirect(url_for('tasks.tasks'))
    
    conn.close()
    return render_template('edit_task.html', 
                         task=task, 
                         clients=clients, 
                         trainers=trainers,
                         available_payments=available_payments)  # ✅ أضف هذا


@tasks_bp.route('/update_task_status/<int:task_id>', methods=['POST'])
def update_task_status(task_id):
    # ... الكود الموجود ...
    pass


@tasks_bp.route('/update_task_status_form/<int:task_id>', methods=['GET', 'POST'])
def update_task_status_form(task_id):
    # ... الكود الموجود ...
    pass


@tasks_bp.route('/add_note/<int:task_id>', methods=['POST'])
def add_note(task_id):
    # ... الكود الموجود ...
    pass


@tasks_bp.route('/add_note_form/<int:task_id>', methods=['GET', 'POST'])
def add_note_form(task_id):
    # ... الكود الموجود ...
    pass


@tasks_bp.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    # ... الكود الموجود ...
    pass


@tasks_bp.route('/tasks/search')
def search_tasks():
    # ... الكود الموجود ...
    pass


@tasks_bp.route('/group_tasks', methods=['POST'])
def group_tasks():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    client_id = request.form['client_id']
    group_name = request.form['group_name']
    conn = get_db()
    conn.execute('UPDATE tasks SET task_group = ? WHERE client_id = ? AND task_group IS NULL', 
                (group_name, client_id))
    conn.commit()
    conn.close()
    
    flash(f'✅ تم تجميع مهام العميل تحت مجموعة "{group_name}"', 'success')
    return redirect(url_for('clients.client_tasks', client_id=client_id))