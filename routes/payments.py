# routes/payments.py
from flask import render_template, request, redirect, url_for, session, flash, send_file
from datetime import datetime
from models import get_db
from routes import payments_bp
from utils import log_activity
import math
import pandas as pd
from io import BytesIO

@payments_bp.route('/all_payments')
def all_payments():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # ===== خيارات العرض والترقيم =====
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    
    if per_page == 0 or per_page == 999999:
        per_page = 999999
        page = 1
    
    conn = get_db()
    
    # ===== بناء الاستعلام =====
    query = '''
        SELECT client_payments.*, 
               clients.name as client_name, 
               clients.company_name,
               client_modules.name as module_name,
               users.name as created_by_name
        FROM client_payments
        LEFT JOIN clients ON client_payments.client_id = clients.id
        LEFT JOIN client_modules ON client_payments.module_id = client_modules.id
        LEFT JOIN users ON client_payments.created_by = users.id
        WHERE 1=1
    '''
    params = []
    
    if search:
        query += ' AND (clients.name LIKE ? OR clients.company_name LIKE ? OR client_payments.invoice_number LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param])
    
    if status_filter:
        query += ' AND client_payments.status = ?'
        params.append(status_filter)
    
    query += ' ORDER BY client_payments.created_at DESC'
    
    # ===== إجمالي النتائج =====
    count_query = '''
        SELECT COUNT(*) as count
        FROM client_payments
        LEFT JOIN clients ON client_payments.client_id = clients.id
        LEFT JOIN client_modules ON client_payments.module_id = client_modules.id
        LEFT JOIN users ON client_payments.created_by = users.id
        WHERE 1=1
    '''
    count_params = []
    if search:
        count_query += ' AND (clients.name LIKE ? OR clients.company_name LIKE ? OR client_payments.invoice_number LIKE ?)'
        count_params.extend([search_param, search_param, search_param])
    if status_filter:
        count_query += ' AND client_payments.status = ?'
        count_params.append(status_filter)
    
    total = conn.execute(count_query, count_params).fetchone()['count']
    
    # ===== ترقيم =====
    if per_page != 999999:
        query += ' LIMIT ? OFFSET ?'
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
    
    payments = conn.execute(query, params).fetchall()
    
    # ===== إحصائيات =====
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total_count,
            SUM(CASE WHEN status = "مدفوع" THEN amount ELSE 0 END) as total_paid,
            SUM(CASE WHEN status = "معلق" THEN amount ELSE 0 END) as total_pending,
            SUM(CASE WHEN status = "متأخر" THEN amount ELSE 0 END) as total_overdue
        FROM client_payments
    ''').fetchone()
    conn.close()
    
    total_pages = math.ceil(total / per_page) if per_page != 999999 and total > 0 else 1
    per_page_options = [10, 25, 50, 100]
    
    return render_template('all_payments.html', 
                         payments=payments, 
                         stats=stats,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         per_page=per_page,
                         per_page_options=per_page_options,
                         search=search,
                         status_filter=status_filter)


@payments_bp.route('/export_all_payments_excel')
def export_all_payments_excel():
    """تصدير جميع المدفوعات إلى Excel"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    payments = conn.execute('''
        SELECT client_payments.*, 
               clients.name as client_name, 
               clients.company_name,
               client_modules.name as module_name
        FROM client_payments
        LEFT JOIN clients ON client_payments.client_id = clients.id
        LEFT JOIN client_modules ON client_payments.module_id = client_modules.id
        ORDER BY client_payments.created_at DESC
    ''').fetchall()
    conn.close()
    
    data = []
    for p in payments:
        data.append({
            'العميل': p['client_name'],
            'الشركة': p['company_name'] or '',
            'المبلغ': p['amount'],
            'تاريخ الدفع': p['payment_date'],
            'تاريخ الاستحقاق': p['due_date'] or '',
            'طريقة الدفع': p['payment_method'],
            'الحالة': p['status'],
            'رقم الفاتورة': p['invoice_number'] or '',
            'الملاحظات': p['notes'] or ''
        })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='المدفوعات')
    output.seek(0)
    
    return send_file(output, 
                     download_name=f'مدفوعات_{datetime.now().strftime("%Y%m%d")}.xlsx',
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@payments_bp.route('/add_payment_global', methods=['GET', 'POST'])
def add_payment_global():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    clients = conn.execute('SELECT id, name, company_name FROM clients ORDER BY name').fetchall()
    modules = conn.execute('SELECT id, name FROM client_modules ORDER BY name').fetchall()
    
    if request.method == 'POST':
        client_id = request.form['client_id']
        module_id = request.form.get('module_id') or None
        amount = request.form['amount']
        payment_date = request.form['payment_date']
        due_date = request.form.get('due_date')
        payment_method = request.form['payment_method']
        status = request.form['status']
        invoice_number = request.form.get('invoice_number', '')
        notes = request.form.get('notes', '')
        is_installment = request.form.get('is_installment', '0')
        installment_count = request.form.get('installment_count', 1)
        
        client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
        if not client:
            flash('❌ العميل غير موجود', 'danger')
            conn.close()
            return redirect(url_for('payments_bp.add_payment_global'))
        
        cursor = conn.execute('''
            INSERT INTO client_payments 
            (client_id, module_id, amount, payment_date, due_date, 
             payment_method, status, invoice_number, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, module_id, amount, payment_date, due_date, 
              payment_method, status, invoice_number, notes, session['user_id']))
        payment_id = cursor.lastrowid
        
        if is_installment == '1' and int(installment_count) > 1:
            installment_amount = float(amount) / int(installment_count)
            for i in range(int(installment_count)):
                conn.execute('''
                    INSERT INTO payment_installments 
                    (payment_id, installment_number, amount, due_date)
                    VALUES (?, ?, ?, date(?, "+" || ? || " days"))
                ''', (payment_id, i+1, installment_amount, payment_date, (i+1)*30))
        
        conn.commit()
        conn.close()
        
        flash('✅ تم إضافة الدفعة بنجاح', 'success')
        log_activity(session['user_id'], 'إضافة دفعة', f'أضاف دفعة بقيمة {amount} للعميل {client["name"]}')
        return redirect(url_for('payments_bp.all_payments'))
    
    conn.close()
    return render_template('add_payment_global.html', clients=clients, modules=modules)


@payments_bp.route('/edit_payment/<int:payment_id>', methods=['GET', 'POST'])
def edit_payment(payment_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    payment = conn.execute('SELECT * FROM client_payments WHERE id = ?', (payment_id,)).fetchone()
    
    if not payment:
        flash('❌ الدفعة غير موجودة', 'danger')
        conn.close()
        return redirect(url_for('payments_bp.all_payments'))
    
    if request.method == 'POST':
        amount = request.form['amount']
        payment_date = request.form['payment_date']
        due_date = request.form.get('due_date')
        payment_method = request.form['payment_method']
        status = request.form['status']
        invoice_number = request.form.get('invoice_number', '')
        notes = request.form.get('notes', '')
        
        conn.execute('''
            UPDATE client_payments SET 
                amount = ?, payment_date = ?, due_date = ?,
                payment_method = ?, status = ?, invoice_number = ?, notes = ?
            WHERE id = ?
        ''', (amount, payment_date, due_date, payment_method, status, 
              invoice_number, notes, payment_id))
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث الدفعة بنجاح', 'success')
        log_activity(session['user_id'], 'تحديث دفعة', f'حدث دفعة {payment_id}')
        return redirect(url_for('payments_bp.all_payments'))
    
    conn.close()
    return render_template('edit_payment.html', payment=payment)


@payments_bp.route('/delete_payment/<int:payment_id>', methods=['POST'])
def delete_payment(payment_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    payment = conn.execute('SELECT * FROM client_payments WHERE id = ?', (payment_id,)).fetchone()
    if not payment:
        flash('❌ الدفعة غير موجودة', 'danger')
        conn.close()
        return redirect(url_for('payments_bp.all_payments'))
    
    conn.execute('DELETE FROM client_payments WHERE id = ?', (payment_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف الدفعة بنجاح', 'success')
    log_activity(session['user_id'], 'حذف دفعة', f'حذف دفعة {payment_id}')
    return redirect(url_for('payments_bp.all_payments'))


@payments_bp.route('/client_payments/<int:client_id>')
def client_payments(client_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('❌ العميل غير موجود', 'danger')
        conn.close()
        return redirect(url_for('clients.clients'))
    
    payments = conn.execute('''
        SELECT client_payments.*, 
               client_modules.name as module_name,
               users.name as created_by_name,
               GROUP_CONCAT(trainers.name, ', ') as trainer_names
        FROM client_payments
        LEFT JOIN client_modules ON client_payments.module_id = client_modules.id
        LEFT JOIN users ON client_payments.created_by = users.id
        LEFT JOIN client_trainers ON client_payments.client_id = client_trainers.client_id
        LEFT JOIN trainers ON client_trainers.trainer_id = trainers.id
        WHERE client_payments.client_id = ?
        GROUP BY client_payments.id
        ORDER BY client_payments.created_at DESC
    ''', (client_id,)).fetchall()
    
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total_count,
            SUM(CASE WHEN status = "مدفوع" THEN amount ELSE 0 END) as total_paid,
            SUM(CASE WHEN status = "معلق" THEN amount ELSE 0 END) as total_pending,
            SUM(CASE WHEN status = "متأخر" THEN amount ELSE 0 END) as total_overdue
        FROM client_payments
        WHERE client_id = ?
    ''', (client_id,)).fetchone()
    conn.close()
    
    return render_template('client_payments.html', 
                         client=client, 
                         payments=payments,
                         stats=stats)