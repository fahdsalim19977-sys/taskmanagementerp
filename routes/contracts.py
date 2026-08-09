# routes/contracts.py
from flask import render_template, request, redirect, url_for, session, flash, send_file, current_app
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os
import math
from models import get_db
from routes import contracts_bp
from utils import log_activity, get_company_settings

@contracts_bp.route('/contracts')
def contracts():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # ===== الحصول على معاملات الفلترة والترقيم =====
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    payment_filter = request.args.get('payment_status', '')
    
    # ===== تحديد عدد العناصر في الصفحة =====
    if per_page == 0 or per_page == 999999:
        per_page = 999999
        page = 1
    
    conn = get_db()
    
    # ===== بناء الاستعلام الأساسي =====
    query = '''
        SELECT client_contracts.*, 
               clients.name as client_name,
               clients.company_name,
               contract_types.name as contract_type_name,
               users.name as created_by_name
        FROM client_contracts
        JOIN clients ON client_contracts.client_id = clients.id
        LEFT JOIN contract_types ON client_contracts.contract_type_id = contract_types.id
        JOIN users ON client_contracts.created_by = users.id
        WHERE 1=1
    '''
    params = []
    
    # ===== البحث =====
    if search:
        query += ' AND (client_contracts.contract_number LIKE ? OR client_contracts.title LIKE ? OR clients.name LIKE ? OR clients.company_name LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param, search_param])
    
    # ===== فلترة حسب حالة العقد =====
    if status_filter:
        query += ' AND client_contracts.status = ?'
        params.append(status_filter)
    
    # ===== فلترة حسب حالة الدفع =====
    if payment_filter:
        query += ' AND client_contracts.payment_status = ?'
        params.append(payment_filter)
    
    # ===== إجمالي النتائج =====
    count_query = '''
        SELECT COUNT(*) as count
        FROM client_contracts
        JOIN clients ON client_contracts.client_id = clients.id
        LEFT JOIN contract_types ON client_contracts.contract_type_id = contract_types.id
        JOIN users ON client_contracts.created_by = users.id
        WHERE 1=1
    '''
    
    count_params = []
    if search:
        count_query += ' AND (client_contracts.contract_number LIKE ? OR client_contracts.title LIKE ? OR clients.name LIKE ? OR clients.company_name LIKE ?)'
        search_param = f'%{search}%'
        count_params.extend([search_param, search_param, search_param, search_param])
    if status_filter:
        count_query += ' AND client_contracts.status = ?'
        count_params.append(status_filter)
    if payment_filter:
        count_query += ' AND client_contracts.payment_status = ?'
        count_params.append(payment_filter)
    
    total = conn.execute(count_query, count_params).fetchone()['count']
    
    # ===== ترتيب وترقيم =====
    query += ' ORDER BY client_contracts.created_at DESC'
    
    if per_page != 999999:
        query += ' LIMIT ? OFFSET ?'
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
    
    contracts_list = conn.execute(query, params).fetchall()
    conn.close()
    
    # ===== حساب عدد الصفحات =====
    if per_page == 999999:
        total_pages = 1
    else:
        total_pages = math.ceil(total / per_page) if total > 0 else 1
    
    # ===== إحصائيات سريعة للفلترة =====
    conn = get_db()
    stats = {
        'total': conn.execute('SELECT COUNT(*) as count FROM client_contracts').fetchone()['count'],
        'active': conn.execute('SELECT COUNT(*) as count FROM client_contracts WHERE status = "نشط"').fetchone()['count'],
        'pending': conn.execute('SELECT COUNT(*) as count FROM client_contracts WHERE status = "معلق"').fetchone()['count'],
        'completed': conn.execute('SELECT COUNT(*) as count FROM client_contracts WHERE status = "منتهي"').fetchone()['count'],
        'paid_full': conn.execute('SELECT COUNT(*) as count FROM client_contracts WHERE payment_status = "مدفوع بالكامل"').fetchone()['count'],
        'partial': conn.execute('SELECT COUNT(*) as count FROM client_contracts WHERE payment_status = "مدفوع جزئيا"').fetchone()['count'],
        'unpaid': conn.execute('SELECT COUNT(*) as count FROM client_contracts WHERE payment_status = "غير مدفوع"').fetchone()['count']
    }
    conn.close()
    
    per_page_options = [10, 25, 50, 100]
    
    return render_template('contracts.html', 
                         contracts=contracts_list,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         per_page=per_page,
                         per_page_options=per_page_options,
                         search=search,
                         status_filter=status_filter,
                         payment_filter=payment_filter,
                         stats=stats)


@contracts_bp.route('/add_contract', methods=['GET', 'POST'])
def add_contract():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    clients = conn.execute('SELECT id, name, company_name FROM clients ORDER BY name').fetchall()
    contract_types = conn.execute('SELECT id, name FROM contract_types WHERE is_active = 1 ORDER BY name').fetchall()
    module_types = conn.execute('SELECT id, name, price FROM module_types WHERE is_active = 1 ORDER BY name').fetchall()
    
    if request.method == 'POST':
        client_id = request.form['client_id']
        contract_type_id = request.form.get('contract_type_id') or None
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
        module_ids = request.form.getlist('module_ids')
        
        check = conn.execute('SELECT * FROM client_contracts WHERE contract_number = ?', (contract_number,)).fetchone()
        if check:
            flash('❌ رقم العقد موجود مسبقاً', 'danger')
            conn.close()
            return render_template('add_contract.html', clients=clients, contract_types=contract_types, module_types=module_types)
        
        cursor = conn.execute('''
            INSERT INTO client_contracts 
            (client_id, contract_type_id, contract_number, title, description, start_date, end_date, 
             contract_value, total_amount, paid_amount, payment_status, status, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'غير مدفوع', ?, ?, ?)
        ''', (client_id, contract_type_id, contract_number, title, description, start_date, end_date, 
              contract_value, total_amount, status, notes, session['user_id']))
        contract_id = cursor.lastrowid
        
        for module_id in module_ids:
            if module_id:
                module = conn.execute('SELECT price FROM module_types WHERE id = ?', (module_id,)).fetchone()
                price = module['price'] if module else 0
                conn.execute('''
                    INSERT INTO contract_modules (contract_id, module_type_id, price)
                    VALUES (?, ?, ?)
                ''', (contract_id, module_id, price))
        
        installment_count = int(request.form.get('installment_count', 0))
        for i in range(1, installment_count + 1):
            amount = request.form.get(f'installment_amount_{i}', 0)
            due_date = request.form.get(f'installment_due_date_{i}', '')
            note = request.form.get(f'installment_notes_{i}', '')
            if due_date and float(amount) > 0:
                conn.execute('''
                    INSERT INTO contract_payments 
                    (contract_id, installment_number, amount, paid_amount, due_date, notes, status)
                    VALUES (?, ?, ?, 0, ?, ?, 'مستحقة')
                ''', (contract_id, i, amount, due_date, note))
        
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
                attachments_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'contracts', str(contract_id))
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
        return redirect(url_for('contracts.contracts'))
    
    conn.close()
    return render_template('add_contract.html', clients=clients, contract_types=contract_types, module_types=module_types)


@contracts_bp.route('/edit_contract/<int:contract_id>', methods=['GET', 'POST'])
def edit_contract(contract_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    contract = conn.execute('SELECT * FROM client_contracts WHERE id = ?', (contract_id,)).fetchone()
    if not contract:
        flash('❌ العقد غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts.contracts'))
    
    clients = conn.execute('SELECT id, name, company_name FROM clients ORDER BY name').fetchall()
    contract_types = conn.execute('SELECT id, name FROM contract_types WHERE is_active = 1 ORDER BY name').fetchall()
    
    if request.method == 'POST':
        client_id = request.form['client_id']
        contract_type_id = request.form.get('contract_type_id') or None
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
            return render_template('edit_contract.html', contract=contract, clients=clients, contract_types=contract_types)
        
        conn.execute('''
            UPDATE client_contracts SET 
                client_id = ?, contract_type_id = ?, contract_number = ?, title = ?, description = ?,
                start_date = ?, end_date = ?, contract_value = ?, status = ?, notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (client_id, contract_type_id, contract_number, title, description, start_date, end_date, 
              contract_value, status, notes, contract_id))
        
        conn.execute('DELETE FROM contract_payments WHERE contract_id = ?', (contract_id,))
        
        installment_count = int(request.form.get('installment_count', 0))
        total_amount = float(request.form.get('total_amount', 0))
        
        if installment_count > 0 and total_amount > 0:
            installment_amount = total_amount / installment_count
            base_date = datetime.now().date()
            
            for i in range(1, installment_count + 1):
                amount = request.form.get(f'installment_amount_{i}', installment_amount)
                due_date = request.form.get(f'installment_due_date_{i}', '')
                note = request.form.get(f'installment_notes_{i}', '')
                
                if not due_date:
                    future_date = base_date + timedelta(days=i*30)
                    due_date = future_date.strftime('%Y-%m-%d')
                
                if float(amount) > 0:
                    conn.execute('''
                        INSERT INTO contract_payments 
                        (contract_id, installment_number, amount, paid_amount, due_date, notes, status)
                        VALUES (?, ?, ?, 0, ?, ?, 'مستحقة')
                    ''', (contract_id, i, amount, due_date, note))
        
        total_paid = conn.execute('''
            SELECT SUM(paid_amount) as total FROM contract_payments WHERE contract_id = ?
        ''', (contract_id,)).fetchone()['total'] or 0
        
        if total_amount == 0:
            payment_status = 'غير مدفوع'
        elif total_paid >= total_amount:
            payment_status = 'مدفوع بالكامل'
        elif total_paid > 0:
            payment_status = 'مدفوع جزئيا'
        else:
            payment_status = 'غير مدفوع'
        
        conn.execute('''
            UPDATE client_contracts 
            SET total_amount = ?, paid_amount = ?, payment_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (total_amount, total_paid, payment_status, contract_id))
        
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث العقد بنجاح', 'success')
        log_activity(session['user_id'], 'تحديث عقد', f'حدث عقد {contract_number}')
        return redirect(url_for('contracts.contracts'))
    
    contract_payments = conn.execute('''
        SELECT * FROM contract_payments WHERE contract_id = ? ORDER BY installment_number ASC
    ''', (contract_id,)).fetchall()
    conn.close()
    
    return render_template('edit_contract.html', 
                         contract=contract, 
                         clients=clients, 
                         contract_types=contract_types,
                         contract_payments=contract_payments)


@contracts_bp.route('/delete_contract/<int:contract_id>', methods=['POST'])
def delete_contract(contract_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    contract = conn.execute('SELECT * FROM client_contracts WHERE id = ?', (contract_id,)).fetchone()
    if not contract:
        flash('❌ العقد غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts.contracts'))
    
    conn.execute('DELETE FROM client_contracts WHERE id = ?', (contract_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف العقد بنجاح', 'success')
    log_activity(session['user_id'], 'حذف عقد', f'حذف عقد {contract["contract_number"]}')
    return redirect(url_for('contracts.contracts'))


@contracts_bp.route('/contract/<int:contract_id>')
def contract_details(contract_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    contract = conn.execute('''
        SELECT client_contracts.*, 
               clients.name as client_name,
               clients.company_name,
               clients.phone as client_phone,
               clients.email as client_email,
               contract_types.name as contract_type_name,
               users.name as created_by_name
        FROM client_contracts
        JOIN clients ON client_contracts.client_id = clients.id
        LEFT JOIN contract_types ON client_contracts.contract_type_id = contract_types.id
        JOIN users ON client_contracts.created_by = users.id
        WHERE client_contracts.id = ?
    ''', (contract_id,)).fetchone()
    
    if not contract:
        flash('❌ العقد غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts.contracts'))
    
    contract_modules = conn.execute('''
        SELECT contract_modules.*, 
               module_types.name as module_name,
               module_types.description as module_description
        FROM contract_modules
        JOIN module_types ON contract_modules.module_type_id = module_types.id
        WHERE contract_modules.contract_id = ?
        ORDER BY module_types.name
    ''', (contract_id,)).fetchall()
    
    attachments = conn.execute('''
        SELECT contract_attachments.*, users.name as uploaded_by_name
        FROM contract_attachments
        JOIN users ON contract_attachments.uploaded_by = users.id
        WHERE contract_attachments.contract_id = ?
        ORDER BY contract_attachments.created_at DESC
    ''', (contract_id,)).fetchall()
    
    payments = conn.execute('''
        SELECT * FROM contract_payments 
        WHERE contract_id = ?
        ORDER BY installment_number ASC
    ''', (contract_id,)).fetchall()
    
    conn.close()
    
    return render_template('contract_details.html', 
                         contract=contract,
                         contract_modules=contract_modules,
                         contract_attachments=attachments,
                         contract_payments=payments)


@contracts_bp.route('/print_contract/<int:contract_id>')
def print_contract(contract_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    contract = conn.execute('''
        SELECT client_contracts.*, 
               clients.name as client_name,
               clients.company_name,
               clients.phone as client_phone,
               clients.email as client_email,
               contract_types.name as contract_type_name,
               users.name as created_by_name
        FROM client_contracts
        JOIN clients ON client_contracts.client_id = clients.id
        LEFT JOIN contract_types ON client_contracts.contract_type_id = contract_types.id
        JOIN users ON client_contracts.created_by = users.id
        WHERE client_contracts.id = ?
    ''', (contract_id,)).fetchone()
    
    if not contract:
        flash('❌ العقد غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts.contracts'))
    
    payments = conn.execute('''
        SELECT * FROM contract_payments 
        WHERE contract_id = ?
        ORDER BY installment_number ASC
    ''', (contract_id,)).fetchall()
    
    settings = conn.execute('SELECT * FROM company_settings LIMIT 1').fetchone()
    conn.close()
    
    return render_template('print_contract.html',
                         contract=contract,
                         contract_payments=payments,
                         settings=settings,
                         today=datetime.now().date())


@contracts_bp.route('/print_all_contracts')
def print_all_contracts():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    contracts = conn.execute('''
        SELECT client_contracts.*, 
               clients.name as client_name,
               clients.company_name,
               contract_types.name as contract_type_name
        FROM client_contracts
        JOIN clients ON client_contracts.client_id = clients.id
        LEFT JOIN contract_types ON client_contracts.contract_type_id = contract_types.id
        ORDER BY client_contracts.created_at DESC
    ''').fetchall()
    
    settings = conn.execute('SELECT * FROM company_settings LIMIT 1').fetchone()
    conn.close()
    
    return render_template('print_all_contracts.html',
                         contracts=contracts,
                         settings=settings,
                         today=datetime.now().date())


@contracts_bp.route('/contracts/filter/<status>')
def contracts_filter(status):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    status_map = {
        'paid_full': 'مدفوع بالكامل',
        'partial': 'مدفوع جزئيا',
        'unpaid': 'غير مدفوع'
    }
    
    status_text = status_map.get(status, '')
    if not status_text:
        flash('❌ حالة غير صحيحة', 'danger')
        return redirect(url_for('contracts.contracts'))
    
    conn = get_db()
    contracts_list = conn.execute('''
        SELECT client_contracts.*, 
               clients.name as client_name,
               clients.company_name,
               contract_types.name as contract_type_name,
               users.name as created_by_name
        FROM client_contracts
        JOIN clients ON client_contracts.client_id = clients.id
        LEFT JOIN contract_types ON client_contracts.contract_type_id = contract_types.id
        JOIN users ON client_contracts.created_by = users.id
        WHERE client_contracts.payment_status = ?
        ORDER BY client_contracts.created_at DESC
    ''', (status_text,)).fetchall()
    conn.close()
    
    titles = {
        'paid_full': 'العقود المدفوعة بالكامل',
        'partial': 'العقود المدفوعة جزئياً',
        'unpaid': 'العقود غير المدفوعة'
    }
    
    return render_template('contracts_filter.html', 
                         contracts=contracts_list,
                         filter_title=titles.get(status, ''),
                         filter_status=status)


# ===== مرفقات العقود =====

@contracts_bp.route('/add_contract_attachment/<int:contract_id>', methods=['POST'])
def add_contract_attachment(contract_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    contract = conn.execute('SELECT * FROM client_contracts WHERE id = ?', (contract_id,)).fetchone()
    if not contract:
        flash('❌ العقد غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts.contracts'))
    
    if 'attachment' not in request.files:
        flash('❌ لم يتم اختيار ملف', 'danger')
        conn.close()
        return redirect(url_for('contracts.contract_details', contract_id=contract_id))
    
    file = request.files['attachment']
    if file.filename == '':
        flash('❌ لم يتم اختيار ملف', 'danger')
        conn.close()
        return redirect(url_for('contracts.contract_details', contract_id=contract_id))
    
    description = request.form.get('description', '')
    
    filename = secure_filename(file.filename)
    name_parts = filename.rsplit('.', 1)
    if len(name_parts) > 1:
        filename = f"{name_parts[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{name_parts[1]}"
    else:
        filename = f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    attachments_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'contracts', str(contract_id))
    os.makedirs(attachments_folder, exist_ok=True)
    file_path = os.path.join(attachments_folder, filename)
    file.save(file_path)
    
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
    return redirect(url_for('contracts.contract_details', contract_id=contract_id))


@contracts_bp.route('/download_contract_attachment/<int:attachment_id>')
def download_contract_attachment(attachment_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    attachment = conn.execute('SELECT * FROM contract_attachments WHERE id = ?', (attachment_id,)).fetchone()
    if not attachment:
        flash('❌ المرفق غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts.contracts'))
    
    conn.close()
    
    if os.path.exists(attachment['file_path']):
        return send_file(attachment['file_path'], 
                       as_attachment=True, 
                       download_name=attachment['file_name'])
    else:
        flash('❌ الملف غير موجود على السيرفر', 'danger')
        return redirect(request.referrer or url_for('contracts.contracts'))


@contracts_bp.route('/delete_contract_attachment/<int:attachment_id>', methods=['POST'])
def delete_contract_attachment(attachment_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    attachment = conn.execute('SELECT * FROM contract_attachments WHERE id = ?', (attachment_id,)).fetchone()
    if not attachment:
        flash('❌ المرفق غير موجود', 'danger')
        conn.close()
        return redirect(url_for('contracts.contracts'))
    
    if os.path.exists(attachment['file_path']):
        try:
            os.remove(attachment['file_path'])
        except Exception as e:
            print(f"Error deleting file: {e}")
    
    conn.execute('DELETE FROM contract_attachments WHERE id = ?', (attachment_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف المرفق بنجاح', 'success')
    log_activity(session['user_id'], 'حذف مرفق عقد', f'حذف {attachment["file_name"]}')
    return redirect(request.referrer or url_for('contracts.contracts'))


@contracts_bp.route('/mark_payment_paid/<int:payment_id>', methods=['POST'])
def mark_payment_paid(payment_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    payment = conn.execute('SELECT * FROM contract_payments WHERE id = ?', (payment_id,)).fetchone()
    if not payment:
        flash('❌ الدفعة غير موجودة', 'danger')
        conn.close()
        return redirect(url_for('contracts.contracts'))
    
    current_paid = payment['paid_amount'] or 0
    paid_amount = request.form.get('paid_amount', 0)
    try:
        paid_amount = float(paid_amount)
    except:
        paid_amount = 0
    
    payment_date = request.form.get('payment_date', '')
    if not payment_date:
        payment_date = datetime.now().strftime('%Y-%m-%d')
    
    current_remaining = payment['amount'] - current_paid
    
    if paid_amount > current_remaining:
        flash(f'❌ المبلغ المدفوع ({paid_amount} ر.س) لا يمكن أن يتجاوز المتبقي ({current_remaining} ر.س)', 'danger')
        conn.close()
        return redirect(request.referrer or url_for('contracts.contracts'))
    
    if paid_amount <= 0:
        flash('❌ المبلغ المدفوع يجب أن يكون أكبر من صفر', 'danger')
        conn.close()
        return redirect(request.referrer or url_for('contracts.contracts'))
    
    new_paid_amount = current_paid + paid_amount
    
    if new_paid_amount >= payment['amount']:
        status = 'مدفوعة'
    else:
        status = 'مدفوعة جزئيا'
    
    conn.execute('''
        UPDATE contract_payments 
        SET paid_amount = ?, status = ?, payment_date = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (new_paid_amount, status, payment_date, payment_id))
    
    contract_id = payment['contract_id']
    
    total_paid = conn.execute('''
        SELECT SUM(paid_amount) as total FROM contract_payments 
        WHERE contract_id = ?
    ''', (contract_id,)).fetchone()['total'] or 0
    
    contract = conn.execute('SELECT total_amount, contract_value FROM client_contracts WHERE id = ?', (contract_id,)).fetchone()
    total = contract['total_amount'] or contract['contract_value'] or 0
    
    paid_full_count = conn.execute('''
        SELECT COUNT(*) as count FROM contract_payments 
        WHERE contract_id = ? AND status = 'مدفوعة'
    ''', (contract_id,)).fetchone()['count']
    
    total_installments = conn.execute('''
        SELECT COUNT(*) as count FROM contract_payments 
        WHERE contract_id = ?
    ''', (contract_id,)).fetchone()['count']
    
    if total == 0:
        payment_status = 'غير مدفوع'
    elif total_paid >= total:
        payment_status = 'مدفوع بالكامل'
    elif total_paid > 0:
        payment_status = 'مدفوع جزئيا'
    else:
        payment_status = 'غير مدفوع'
    
    print(f"📊 تحديث حالة العقد {contract_id}: total={total}, total_paid={total_paid}, status={payment_status}")
    
    conn.execute('''
        UPDATE client_contracts 
        SET paid_amount = ?, payment_status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (total_paid, payment_status, contract_id))
    
    conn.commit()
    conn.close()
    
    flash(f'✅ تم تسجيل دفعة بقيمة {paid_amount} ر.س بنجاح', 'success')
    log_activity(session['user_id'], 'تسجيل دفعة', f'تم استلام {paid_amount} ر.س للدفعة {payment["installment_number"]}')
    return redirect(request.referrer or url_for('contracts.contracts'))