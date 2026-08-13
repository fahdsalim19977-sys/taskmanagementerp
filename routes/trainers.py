# routes/trainers.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import get_db
import sqlite3
import math

trainers_bp = Blueprint('trainers', __name__, url_prefix='/trainers')

# ===== عرض قائمة المدربين =====
@trainers_bp.route('/')
def index():
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
    
    # ===== إجمالي النتائج =====
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
    
    # ===== ترقيم =====
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


# ===== عرض تفاصيل مدرب =====
@trainers_bp.route('/<int:trainer_id>')
def details(trainer_id):
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


# ===== إضافة مدرب جديد =====
@trainers_bp.route('/add', methods=['GET', 'POST'])
def add():
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
        return redirect(url_for('trainers.index'))
    
    return render_template('add_trainer.html')


# ===== تعديل مدرب =====
@trainers_bp.route('/edit/<int:trainer_id>', methods=['GET', 'POST'])
def edit(trainer_id):
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
        return redirect(url_for('trainers.details', trainer_id=trainer_id))
    
    conn.close()
    return render_template('edit_trainer.html', trainer=trainer)


# ===== حذف مدرب =====
@trainers_bp.route('/delete/<int:trainer_id>', methods=['POST'])
def delete(trainer_id):
    conn = get_db()
    
    clients = conn.execute('SELECT COUNT(*) as count FROM client_trainers WHERE trainer_id = ?', (trainer_id,)).fetchone()
    
    if clients['count'] > 0:
        flash('لا يمكن حذف المدرب لأنه مرتبط بعملاء', 'error')
        conn.close()
        return redirect(url_for('trainers.details', trainer_id=trainer_id))
    
    conn.execute('DELETE FROM trainers WHERE id = ?', (trainer_id,))
    conn.commit()
    conn.close()
    
    flash('تم حذف المدرب بنجاح', 'success')
    return redirect(url_for('trainers.index'))