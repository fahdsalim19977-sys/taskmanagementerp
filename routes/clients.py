# routes/clients.py
from flask import render_template, request, redirect, url_for, session, flash
from models import get_db
from routes import clients_bp
from utils import get_trainers, check_role, log_activity

@clients_bp.route('/clients')
def clients():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    clients_list = conn.execute('''
        SELECT clients.*, 
               GROUP_CONCAT(trainers.name, ', ') as trainer_names
        FROM clients
        LEFT JOIN client_trainers ON clients.id = client_trainers.client_id
        LEFT JOIN trainers ON client_trainers.trainer_id = trainers.id
        GROUP BY clients.id
        ORDER BY clients.name
    ''').fetchall()
    conn.close()
    return render_template('clients.html', clients=clients_list)

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
        return redirect(url_for('clients_bp.clients'))
    
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
        return redirect(url_for('clients_bp.clients'))
    
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
        return redirect(url_for('clients_bp.clients'))
    
    conn.close()
    return render_template('edit_client.html', client=client, trainers=trainers, 
                         current_trainer_ids=current_trainer_ids)

@clients_bp.route('/delete_client/<int:client_id>', methods=['POST'])
def delete_client(client_id):
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('clients_bp.clients'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('❌ العميل غير موجود', 'danger')
        conn.close()
        return redirect(url_for('clients_bp.clients'))
    
    conn.execute('DELETE FROM clients WHERE id = ?', (client_id,))
    conn.execute('DELETE FROM client_trainers WHERE client_id = ?', (client_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف العميل بنجاح', 'success')
    log_activity(session['user_id'], 'حذف عميل', f'حذف عميل رقم {client_id}')
    return redirect(url_for('clients_bp.clients'))