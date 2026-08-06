# routes/reports.py
from flask import render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
from models import get_db
from routes import reports_bp
from utils import check_role

@reports_bp.route('/reports')
def reports():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    total_tasks = conn.execute('SELECT COUNT(*) as count FROM tasks').fetchone()['count']
    completed_count = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "مكتملة"').fetchone()['count']
    in_progress_count = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "قيد التنفيذ"').fetchone()['count']
    overdue_count = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE due_date < date("now") AND status != "مكتملة"').fetchone()['count']
    
    total_payments_count = conn.execute('SELECT COUNT(*) as count FROM client_payments').fetchone()['count']
    total_payments_amount = conn.execute('SELECT SUM(amount) as total FROM client_payments').fetchone()['total'] or 0
    paid_count = conn.execute('SELECT COUNT(*) as count FROM client_payments WHERE status = "مدفوع"').fetchone()['count']
    pending_count = conn.execute('SELECT COUNT(*) as count FROM client_payments WHERE status = "معلق"').fetchone()['count']
    overdue_payments_count = conn.execute('SELECT COUNT(*) as count FROM client_payments WHERE status = "متأخر"').fetchone()['count']
    
    total_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع"').fetchone()['total'] or 0
    monthly_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع" AND payment_date >= date("now", "-30 days")').fetchone()['total'] or 0
    weekly_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع" AND payment_date >= date("now", "-7 days")').fetchone()['total'] or 0
    daily_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع" AND payment_date >= date("now", "-1 day")').fetchone()['total'] or 0
    
    conn.close()
    return render_template('reports.html',
                         total_tasks=total_tasks,
                         completed_count=completed_count,
                         in_progress_count=in_progress_count,
                         overdue_count=overdue_count,
                         total_payments_count=total_payments_count,
                         total_payments_amount=total_payments_amount,
                         paid_count=paid_count,
                         pending_count=pending_count,
                         overdue_payments_count=overdue_payments_count,
                         total_revenue=total_revenue,
                         monthly_revenue=monthly_revenue,
                         weekly_revenue=weekly_revenue,
                         daily_revenue=daily_revenue)

@reports_bp.route('/revenue_report')
def revenue_report():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    total_revenue = conn.execute('SELECT SUM(amount) as total FROM client_payments WHERE status = "مدفوع"').fetchone()['total'] or 0
    revenue_by_client = conn.execute('''
        SELECT clients.name, 
               SUM(client_payments.amount) as total,
               COUNT(client_payments.id) as count
        FROM client_payments
        JOIN clients ON client_payments.client_id = clients.id
        WHERE client_payments.status = "مدفوع"
        GROUP BY clients.id
        ORDER BY total DESC
        LIMIT 10
    ''').fetchall()
    revenue_by_month = conn.execute('''
        SELECT strftime("%Y-%m", payment_date) as month,
               SUM(amount) as total
        FROM client_payments
        WHERE status = "مدفوع"
        GROUP BY strftime("%Y-%m", payment_date)
        ORDER BY month DESC
        LIMIT 12
    ''').fetchall()
    conn.close()
    return render_template('revenue_report.html',
                         total_revenue=total_revenue,
                         revenue_by_client=revenue_by_client,
                         revenue_by_month=revenue_by_month)

@reports_bp.route('/contracts_report')
def contracts_report():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    contract_types = conn.execute('SELECT * FROM contract_types WHERE is_active = 1 ORDER BY name').fetchall()
    
    query = '''
        SELECT client_contracts.*, 
               clients.name as client_name,
               clients.company_name,
               contract_types.name as contract_type_name,
               (SELECT COUNT(*) FROM contract_payments WHERE contract_payments.contract_id = client_contracts.id) as payments_count
        FROM client_contracts
        JOIN clients ON client_contracts.client_id = clients.id
        LEFT JOIN contract_types ON client_contracts.contract_type_id = contract_types.id
        WHERE 1=1
    '''
    params = []
    
    contract_type = request.args.get('contract_type')
    if contract_type:
        query += ' AND client_contracts.contract_type_id = ?'
        params.append(contract_type)
    
    date_from = request.args.get('date_from')
    if date_from:
        query += ' AND client_contracts.start_date >= ?'
        params.append(date_from)
    
    date_to = request.args.get('date_to')
    if date_to:
        query += ' AND client_contracts.end_date <= ?'
        params.append(date_to)
    
    query += ' ORDER BY client_contracts.created_at DESC'
    
    contracts = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('contracts_report.html', 
                         contracts=contracts,
                         contract_types=contract_types)

@reports_bp.route('/contract_payments_report/<int:contract_id>')
def contract_payments_report(contract_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    try:
        conn = get_db()
        
        contract = conn.execute('''
            SELECT client_contracts.*, clients.name as client_name
            FROM client_contracts
            JOIN clients ON client_contracts.client_id = clients.id
            WHERE client_contracts.id = ?
        ''', (contract_id,)).fetchone()
        
        if not contract:
            flash('❌ العقد غير موجود', 'danger')
            conn.close()
            return redirect(url_for('reports_bp.contracts_report'))
        
        payments = conn.execute('''
            SELECT * FROM contract_payments 
            WHERE contract_id = ?
            ORDER BY installment_number ASC
        ''', (contract_id,)).fetchall()
        
        conn.close()
        
        total_paid = sum(p['paid_amount'] or 0 for p in payments if p['status'] in ('مدفوعة', 'مدفوعة جزئيا'))
        total_due = sum(p['amount'] for p in payments if p['status'] == 'مستحقة')
        total_overdue = sum(p['amount'] for p in payments if p['status'] == 'متأخرة')
        
        return render_template('contract_payments_report.html', 
                             contract=contract, 
                             payments=payments,
                             total_paid=total_paid,
                             total_due=total_due,
                             total_overdue=total_overdue)
    except Exception as e:
        print(f"❌ خطأ في contract_payments_report: {e}")
        import traceback
        traceback.print_exc()
        flash(f'❌ حدث خطأ: {str(e)}', 'danger')
        return redirect(url_for('reports_bp.contracts_report'))

@reports_bp.route('/advanced_reports')
def advanced_reports():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    
    # ===== توقعات الإيرادات =====
    revenue_forecast = []
    for i in range(1, 7):
        month = (datetime.now().replace(day=1) + timedelta(days=i*30)).strftime('%Y-%m')
        expected = conn.execute('''
            SELECT SUM(total_amount) as total FROM client_contracts 
            WHERE strftime('%Y-%m', end_date) = ?
        ''', (month,)).fetchone()['total'] or 0
        
        paid = conn.execute('''
            SELECT SUM(paid_amount) as total FROM client_contracts 
            WHERE strftime('%Y-%m', end_date) = ?
        ''', (month,)).fetchone()['total'] or 0
        
        remaining = expected - paid
        percentage = round((paid / expected * 100) if expected > 0 else 0, 1)
        
        revenue_forecast.append({
            'month': month,
            'expected': expected,
            'paid': paid,
            'remaining': remaining,
            'percentage': percentage
        })
    
    # ===== أفضل العملاء =====
    top_clients = []
    top_clients_data = conn.execute('''
        SELECT clients.id, clients.name,
               COUNT(client_contracts.id) as contracts_count,
               SUM(client_contracts.total_amount) as total_amount,
               SUM(client_contracts.paid_amount) as paid_amount
        FROM clients
        JOIN client_contracts ON clients.id = client_contracts.client_id
        GROUP BY clients.id
        ORDER BY total_amount DESC
        LIMIT 10
    ''').fetchall()
    
    for row in top_clients_data:
        top_clients.append({
            'id': row['id'],
            'name': row['name'],
            'contracts_count': row['contracts_count'],
            'total_amount': row['total_amount'] or 0,
            'paid_amount': row['paid_amount'] or 0,
            'remaining': (row['total_amount'] or 0) - (row['paid_amount'] or 0)
        })
    
    # ===== أداء المدربين =====
    trainer_performance = []
    trainer_data = conn.execute('''
        SELECT trainers.id, trainers.name,
               COUNT(DISTINCT client_trainers.client_id) as clients_count,
               COUNT(tasks.id) as tasks_count,
               SUM(CASE WHEN tasks.status = 'مكتملة' THEN 1 ELSE 0 END) as completed_tasks
        FROM trainers
        LEFT JOIN client_trainers ON trainers.id = client_trainers.trainer_id
        LEFT JOIN clients ON client_trainers.client_id = clients.id
        LEFT JOIN tasks ON clients.id = tasks.client_id
        GROUP BY trainers.id
        ORDER BY tasks_count DESC
    ''').fetchall()
    
    for row in trainer_data:
        tasks_count = row['tasks_count'] or 0
        completed = row['completed_tasks'] or 0
        completion_rate = round((completed / tasks_count * 100) if tasks_count > 0 else 0, 1)
        
        trainer_performance.append({
            'id': row['id'],
            'name': row['name'],
            'clients_count': row['clients_count'] or 0,
            'tasks_count': tasks_count,
            'completed_tasks': completed,
            'completion_rate': completion_rate
        })
    
    conn.close()
    
    return render_template('advanced_reports.html',
                         revenue_forecast=revenue_forecast,
                         top_clients=top_clients,
                         trainer_performance=trainer_performance)