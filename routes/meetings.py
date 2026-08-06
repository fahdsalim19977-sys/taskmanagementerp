# routes/meetings.py
from flask import render_template, request, redirect, url_for, session, flash
from models import get_db
from routes import meetings_bp
from utils import log_activity

@meetings_bp.route('/meetings')
def meetings():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    upcoming = conn.execute('''
        SELECT meetings.*, clients.name as client_name, users.name as created_by_name
        FROM meetings
        JOIN clients ON meetings.client_id = clients.id
        JOIN users ON meetings.created_by = users.id
        WHERE meetings.meeting_date >= datetime("now") AND meetings.status = "مجدول"
        ORDER BY meetings.meeting_date ASC
    ''').fetchall()
    
    past = conn.execute('''
        SELECT meetings.*, clients.name as client_name, users.name as created_by_name
        FROM meetings
        JOIN clients ON meetings.client_id = clients.id
        JOIN users ON meetings.created_by = users.id
        WHERE meetings.meeting_date < datetime("now") OR meetings.status != "مجدول"
        ORDER BY meetings.meeting_date DESC
        LIMIT 20
    ''').fetchall()
    conn.close()
    return render_template('meetings.html', upcoming=upcoming, past=past)

@meetings_bp.route('/add_meeting', methods=['GET', 'POST'])
def add_meeting():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    clients = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
    conn.close()
    
    if request.method == 'POST':
        client_id = request.form['client_id']
        title = request.form['title']
        description = request.form['description']
        meeting_date = request.form['meeting_date']
        duration = request.form['duration']
        location = request.form['location']
        meeting_link = request.form['meeting_link']
        
        conn = get_db()
        cursor = conn.execute('''
            INSERT INTO meetings (client_id, title, description, meeting_date, duration, location, meeting_link, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, title, description, meeting_date, duration, location, meeting_link, session['user_id']))
        meeting_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        flash('✅ تم إضافة الموعد بنجاح', 'success')
        log_activity(session['user_id'], 'إضافة موعد', f'أضاف موعد: {title}')
        return redirect(url_for('meetings_bp.meetings'))
    
    return render_template('add_meeting.html', clients=clients)

@meetings_bp.route('/meeting/<int:meeting_id>')
def meeting_details(meeting_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    meeting = conn.execute('''
        SELECT meetings.*, clients.name as client_name, clients.phone as client_phone,
               clients.email as client_email, users.name as created_by_name
        FROM meetings
        JOIN clients ON meetings.client_id = clients.id
        JOIN users ON meetings.created_by = users.id
        WHERE meetings.id = ?
    ''', (meeting_id,)).fetchone()
    tasks = conn.execute('SELECT * FROM tasks WHERE meeting_id = ?', (meeting_id,)).fetchall()
    conn.close()
    return render_template('meeting_details.html', meeting=meeting, tasks=tasks)

@meetings_bp.route('/update_meeting_status/<int:meeting_id>', methods=['POST'])
def update_meeting_status(meeting_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    status = request.form['status']
    conn = get_db()
    conn.execute('UPDATE meetings SET status = ? WHERE id = ?', (status, meeting_id))
    conn.commit()
    conn.close()
    
    flash('✅ تم تحديث حالة الموعد', 'success')
    return redirect(url_for('meetings_bp.meetings'))