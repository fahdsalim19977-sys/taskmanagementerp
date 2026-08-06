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
    
    available_payments = conn.execute('''
        SELECT contract_payments.*, 
               client_contracts.contract_number,
               client_contracts.client_id
        FROM contract_payments
        JOIN client_contracts ON contract_payments.contract_id = client_contracts.id
        WHERE contract_payments.status IN ('مستحقة', 'مدفوعة جزئيا')
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
    
    if request.method == 'POST':
        client_id = request.form['client_id']
        assigned_to = request.form['assigned_to']
        title = request.form['title']
        description = request.form.get('description', '')
        due_date = request.form['due_date']
        priority = request.form['priority']
        estimated_duration = request.form.get('estimated_duration', 0)
        task_group = request.form.get('task_group', '')
        
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
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (client_id, assigned_to, title, description, due_date, priority, 
              estimated_duration, task_group, task_id))
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث التدريب بنجاح', 'success')
        log_activity(session['user_id'], 'تعديل تدريب', f'عدل {title}')
        return redirect(url_for('tasks.tasks'))
    
    conn.close()
    return render_template('edit_task.html', task=task, clients=clients, trainers=trainers)


@tasks_bp.route('/update_task_status/<int:task_id>', methods=['POST'])
def update_task_status(task_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    status = request.form['status']
    completion = request.form.get('completion_percentage', 0)
    actual_duration = request.form.get('actual_duration', 0)
    
    print("=" * 60)
    print(f"🔍 تحديث حالة التدريب {task_id}")
    print(f"   الحالة الجديدة: {status}")
    print("=" * 60)
    
    conn = get_db()
    
    try:
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
        
        print(f"📋 معلومات التدريب:")
        print(f"   العنوان: {task['title']}")
        print(f"   contract_payment_id: {task['contract_payment_id']}")
        print(f"   الحالة الحالية: {task['status']}")
        
        # ===== إذا كان التدريب مكتمل ولديه دفعة مرتبطة =====
        if status == 'مكتملة' and task['contract_payment_id']:
            print("✅ تم اكتشاف تدريب مكتمل مع دفعة مرتبطة")
            
            payment_id = task['contract_payment_id']
            payment = conn.execute('SELECT * FROM contract_payments WHERE id = ?', (payment_id,)).fetchone()
            
            if payment:
                print(f"💳 معلومات الدفعة:")
                print(f"   ID: {payment['id']}")
                print(f"   المبلغ: {payment['amount']}")
                print(f"   الحالة الحالية: {payment['status']}")
                
                if payment['status'] != 'مدفوعة':
                    training_title = task['title']
                    
                    print(f"📝 تحديث الدفعة:")
                    print(f"   الحالة الجديدة: متأخرة")
                    print(f"   الملاحظة: تم التدريب على: {training_title}")
                    
                    conn.execute('''
                        UPDATE contract_payments 
                        SET status = 'متأخرة', 
                            due_date = date('now'),
                            notes = COALESCE(notes, '') || 'تم التدريب على: ' || ?
                        WHERE id = ?
                    ''', (training_title, payment_id))
                    
                    # ===== تحديث حالة العقد =====
                    contract_id = payment['contract_id']
                    
                    has_overdue = conn.execute('''
                        SELECT COUNT(*) as count FROM contract_payments 
                        WHERE contract_id = ? AND status = 'متأخرة'
                    ''', (contract_id,)).fetchone()['count'] > 0
                    
                    if has_overdue:
                        payment_status = 'مدفوع جزئيا'
                    else:
                        total_paid = conn.execute('''
                            SELECT SUM(paid_amount) as total FROM contract_payments 
                            WHERE contract_id = ? AND status = 'مدفوعة'
                        ''', (contract_id,)).fetchone()['total'] or 0
                        
                        contract = conn.execute('SELECT total_amount FROM client_contracts WHERE id = ?', (contract_id,)).fetchone()
                        total = contract['total_amount'] or 0
                        
                        if total_paid >= total:
                            payment_status = 'مدفوع بالكامل'
                        elif total_paid > 0:
                            payment_status = 'مدفوع جزئيا'
                        else:
                            payment_status = 'غير مدفوع'
                    
                    conn.execute('''
                        UPDATE client_contracts 
                        SET payment_status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (payment_status, contract_id))
                    
                    flash(f'✅ تم تفعيل الدفعة رقم {payment["installment_number"]} للعقد (متأخرة)', 'warning')
                    
                    # ===== تسجيل النشاط مع تجاهل الأخطاء =====
                    try:
                        log_activity(session['user_id'], 'تفعيل دفعة من تدريب', 
                                   f'تم تفعيل دفعة {payment_id} من تدريب {task["title"]} (متأخرة)')
                    except Exception as log_error:
                        print(f"⚠️ فشل تسجيل النشاط (سيتم تجاهله): {log_error}")
                    
                    print("✅ تم تحديث الدفعة بنجاح")
                else:
                    print("⚠️ الدفعة مدفوعة بالفعل، لن يتم تحديثها")
            else:
                print("❌ الدفعة غير موجودة")
        else:
            print(f"ℹ️ الشرط غير متحقق: status={status}, contract_payment_id={task['contract_payment_id']}")
        
        # ===== تحديث حالة التدريب =====
        conn.execute('''
            UPDATE tasks SET 
                status = ?, 
                completion_percentage = ?, 
                actual_duration = ?, 
                updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (status, completion, actual_duration, task_id))
        
        conn.commit()
        
        print("✅ تم تحديث حالة التدريب بنجاح")
        print("=" * 60)
        
        try:
            log_activity(session['user_id'], 'تحديث حالة تدريب', f'غير حالة التدريب {task_id}')
        except Exception as e:
            print(f"⚠️ فشل تسجيل النشاط (سيتم تجاهله): {e}")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        flash(f'❌ حدث خطأ: {str(e)}', 'danger')
    finally:
        conn.close()
    
    flash('✅ تم تحديث حالة التدريب بنجاح', 'success')
    return redirect(request.referrer or url_for('tasks.tasks'))


@tasks_bp.route('/update_task_status_form/<int:task_id>', methods=['GET', 'POST'])
def update_task_status_form(task_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    
    if not task:
        flash('❌ التدريب غير موجود', 'danger')
        return redirect(url_for('tasks.tasks'))
    
    if request.method == 'POST':
        return redirect(url_for('update_task_status', task_id=task_id))
    
    return render_template('update_task_status.html', task=task)


@tasks_bp.route('/add_note/<int:task_id>', methods=['POST'])
def add_note(task_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    note = request.form.get('note', '')
    file = request.files.get('attachment')
    
    attachment_path = None
    if file and file.filename:
        filename = secure_filename(file.filename)
        name_parts = filename.rsplit('.', 1)
        if len(name_parts) > 1:
            filename = f"{name_parts[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{name_parts[1]}"
        else:
            filename = f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        attachment_path = file_path
    
    conn = get_db()
    conn.execute('''
        INSERT INTO task_updates (task_id, user_id, note, attachment_path)
        VALUES (?, ?, ?, ?)
    ''', (task_id, session['user_id'], note, attachment_path))
    conn.commit()
    conn.close()
    
    flash('📝 تم إضافة الملاحظة بنجاح', 'success')
    log_activity(session['user_id'], 'إضافة ملاحظة', f'أضاف ملاحظة للتدريب {task_id}')
    return redirect(request.referrer or url_for('tasks.tasks'))


@tasks_bp.route('/add_note_form/<int:task_id>', methods=['GET', 'POST'])
def add_note_form(task_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        note = request.form.get('note', '')
        file = request.files.get('attachment')
        
        attachment_path = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            name_parts = filename.rsplit('.', 1)
            if len(name_parts) > 1:
                filename = f"{name_parts[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{name_parts[1]}"
            else:
                filename = f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            attachment_path = file_path
        
        conn = get_db()
        conn.execute('''
            INSERT INTO task_updates (task_id, user_id, note, attachment_path)
            VALUES (?, ?, ?, ?)
        ''', (task_id, session['user_id'], note, attachment_path))
        conn.commit()
        conn.close()
        
        flash('📝 تم إضافة الملاحظة بنجاح', 'success')
        return redirect(url_for('tasks.tasks'))
    
    return render_template('add_note.html', task_id=task_id)


@tasks_bp.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        flash('❌ التدريب غير موجود', 'danger')
        conn.close()
        return redirect(url_for('tasks.tasks'))
    
    user_role = session['user_role']
    if user_role == 'مراقب':
        flash('⛔ ليس لديك صلاحية لحذف التدريبات', 'danger')
        conn.close()
        return redirect(url_for('tasks.tasks'))
    if user_role == 'موظف' and task['assigned_to'] != session['user_id']:
        flash('⛔ يمكنك حذف تدريباتك فقط', 'danger')
        conn.close()
        return redirect(url_for('tasks.tasks'))
    
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف التدريب بنجاح', 'success')
    log_activity(session['user_id'], 'حذف تدريب', f'حذف تدريب رقم {task_id}')
    return redirect(url_for('tasks.tasks'))


@tasks_bp.route('/tasks/search')
def search_tasks():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    search_term = request.args.get('q', '').strip()
    conn = get_db()
    user_role = session['user_role']
    
    if user_role == 'موظف':
        query = '''
            SELECT tasks.*, clients.name as client_name, clients.company_name, trainers.name as assigned_name 
            FROM tasks 
            JOIN clients ON tasks.client_id = clients.id 
            JOIN trainers ON tasks.assigned_to = trainers.id 
            WHERE tasks.assigned_to = ? AND clients.name LIKE ?
            ORDER BY tasks.due_date ASC
        '''
        params = (session['user_id'], f'%{search_term}%')
    else:
        query = '''
            SELECT tasks.*, clients.name as client_name, clients.company_name, trainers.name as assigned_name 
            FROM tasks 
            JOIN clients ON tasks.client_id = clients.id 
            JOIN trainers ON tasks.assigned_to = trainers.id 
            WHERE clients.name LIKE ?
            ORDER BY tasks.due_date ASC
        '''
        params = (f'%{search_term}%',)
    
    task_list = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('tasks.html', tasks=task_list, today=datetime.now().date(), search_term=search_term)


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