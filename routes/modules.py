# routes/modules.py
from flask import render_template, request, redirect, url_for, session, flash
from models import get_db
from routes import modules_bp
from utils import check_role, log_activity

@modules_bp.route('/module_types')
def module_types():
    """عرض جميع أنواع المديولات"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    types = conn.execute('SELECT * FROM module_types ORDER BY name').fetchall()
    conn.close()
    return render_template('module_types.html', types=types)

@modules_bp.route('/add_module_type', methods=['POST'])
def add_module_type():
    """إضافة نوع مديول جديد"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '')
    price = request.form.get('price', 0)
    
    if not name:
        flash('❌ اسم المديول مطلوب', 'danger')
        return redirect(url_for('modules_bp.module_types'))
    
    conn = get_db()
    conn.execute('''
        INSERT INTO module_types (name, description, price)
        VALUES (?, ?, ?)
    ''', (name, description, price))
    conn.commit()
    conn.close()
    
    flash('✅ تم إضافة نوع المديول بنجاح', 'success')
    log_activity(session['user_id'], 'إضافة نوع مديول', f'أضاف {name}')
    return redirect(url_for('modules_bp.module_types'))

@modules_bp.route('/edit_module_type/<int:type_id>', methods=['POST'])
def edit_module_type(type_id):
    """تعديل نوع مديول"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '')
    price = request.form.get('price', 0)
    is_active = request.form.get('is_active', '1')
    
    conn = get_db()
    conn.execute('''
        UPDATE module_types SET name = ?, description = ?, price = ?, is_active = ?
        WHERE id = ?
    ''', (name, description, price, is_active, type_id))
    conn.commit()
    conn.close()
    
    flash('✅ تم تحديث نوع المديول بنجاح', 'success')
    log_activity(session['user_id'], 'تحديث نوع مديول', f'حدث {name}')
    return redirect(url_for('modules_bp.module_types'))

@modules_bp.route('/delete_module_type/<int:type_id>', methods=['POST'])
def delete_module_type(type_id):
    """حذف نوع مديول"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    conn.execute('DELETE FROM module_types WHERE id = ?', (type_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف نوع المديول بنجاح', 'success')
    log_activity(session['user_id'], 'حذف نوع مديول', f'حذف نوع {type_id}')
    return redirect(url_for('modules_bp.module_types'))

@modules_bp.route('/client_modules/<int:client_id>')
def client_modules(client_id):
    """عرض مديولات العميل"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('❌ العميل غير موجود', 'danger')
        conn.close()
        return redirect(url_for('clients_bp.clients'))
    
    modules = conn.execute('''
        SELECT * FROM client_modules 
        WHERE client_id = ? 
        ORDER BY created_at DESC
    ''', (client_id,)).fetchall()
    conn.close()
    
    return render_template('client_modules.html', client=client, modules=modules)

@modules_bp.route('/add_module/<int:client_id>', methods=['GET', 'POST'])
def add_module(client_id):
    """إضافة مديول للعميل"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('❌ العميل غير موجود', 'danger')
        conn.close()
        return redirect(url_for('clients_bp.clients'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        price = request.form.get('price', 0)
        status = request.form['status']
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        conn.execute('''
            INSERT INTO client_modules (client_id, name, description, price, status, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, name, description, price, status, start_date, end_date))
        conn.commit()
        conn.close()
        
        flash('✅ تم إضافة المديول بنجاح', 'success')
        log_activity(session['user_id'], 'إضافة مديول', f'أضاف {name} للعميل {client["name"]}')
        return redirect(url_for('modules_bp.client_modules', client_id=client_id))
    
    conn.close()
    return render_template('add_module.html', client=client)

@modules_bp.route('/edit_module/<int:module_id>', methods=['GET', 'POST'])
def edit_module(module_id):
    """تعديل مديول"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    module = conn.execute('SELECT * FROM client_modules WHERE id = ?', (module_id,)).fetchone()
    if not module:
        flash('❌ المديول غير موجود', 'danger')
        conn.close()
        return redirect(url_for('modules_bp.all_modules'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        price = request.form.get('price', 0)
        status = request.form['status']
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        conn.execute('''
            UPDATE client_modules SET 
                name = ?, description = ?, price = ?, status = ?, 
                start_date = ?, end_date = ?
            WHERE id = ?
        ''', (name, description, price, status, start_date, end_date, module_id))
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث المديول بنجاح', 'success')
        log_activity(session['user_id'], 'تحديث مديول', f'حدث {name}')
        return redirect(url_for('modules_bp.client_modules', client_id=module['client_id']))
    
    conn.close()
    return render_template('edit_module.html', module=module)

@modules_bp.route('/delete_module/<int:module_id>', methods=['POST'])
def delete_module(module_id):
    """حذف مديول"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    module = conn.execute('SELECT * FROM client_modules WHERE id = ?', (module_id,)).fetchone()
    if not module:
        flash('❌ المديول غير موجود', 'danger')
        conn.close()
        return redirect(url_for('modules_bp.all_modules'))
    
    client_id = module['client_id']
    conn.execute('DELETE FROM client_modules WHERE id = ?', (module_id,))
    conn.commit()
    conn.close()
    
    flash('✅ تم حذف المديول بنجاح', 'success')
    log_activity(session['user_id'], 'حذف مديول', f'حذف {module["name"]}')
    return redirect(url_for('modules_bp.client_modules', client_id=client_id))

@modules_bp.route('/add_module_global', methods=['GET', 'POST'])
def add_module_global():
    """إضافة مديول جديد (من شاشة المديولات العامة)"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    clients = conn.execute('SELECT id, name FROM clients ORDER BY name').fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        client_id = request.form.get('client_id') or None
        price = request.form.get('price', 0)
        status = request.form['status']
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        conn.execute('''
            INSERT INTO client_modules (client_id, name, description, price, status, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, name, description, price, status, start_date, end_date))
        conn.commit()
        conn.close()
        
        flash('✅ تم إضافة المديول بنجاح', 'success')
        log_activity(session['user_id'], 'إضافة مديول', f'أضاف {name}')
        return redirect(url_for('modules_bp.all_modules'))
    
    conn.close()
    return render_template('add_module_global.html', clients=clients)

@modules_bp.route('/all_modules')
def all_modules():
    """عرض جميع المديولات"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    modules = conn.execute('''
        SELECT client_modules.*, 
               clients.name as client_name,
               clients.company_name
        FROM client_modules
        LEFT JOIN clients ON client_modules.client_id = clients.id
        ORDER BY client_modules.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('all_modules.html', modules=modules)