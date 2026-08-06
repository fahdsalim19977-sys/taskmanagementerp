# routes/trainers.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import get_db
import sqlite3

trainers_bp = Blueprint('trainers', __name__, url_prefix='/trainers')

# ===== عرض قائمة المدربين =====
@trainers_bp.route('/')
def index():
    conn = get_db()
    trainers = conn.execute('''
        SELECT t.*, COUNT(ct.client_id) as client_count 
        FROM trainers t
        LEFT JOIN client_trainers ct ON t.id = ct.trainer_id
        GROUP BY t.id
        ORDER BY t.name
    ''').fetchall()
    conn.close()
    
    for trainer in trainers:
        if trainer['client_count'] is None:
            trainer['client_count'] = 0
    
    return render_template('trainers.html', trainers=trainers)


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