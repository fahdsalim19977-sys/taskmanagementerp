# routes/users.py
from flask import render_template, request, redirect, url_for, session, flash
import sqlite3
from models import get_db, hash_password, get_user_permissions, has_permission, add_permission_to_user, remove_permission_from_user
from routes import users_bp
from utils import check_role, log_activity

@users_bp.route('/users')
def users():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    conn = get_db()
    users_list = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('users.html', users=users_list)


@users_bp.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        conn = get_db()
        try:
            conn.execute('INSERT INTO users (username, name, email, password, role) VALUES (?, ?, ?, ?, ?)', 
                        (username, name, email, hash_password(password), role))
            conn.commit()
            flash('✅ تم إضافة المستخدم بنجاح', 'success')
            log_activity(session['user_id'], 'إضافة مستخدم', f'أضاف {username}')
        except sqlite3.IntegrityError:
            flash('❌ اسم المستخدم أو البريد موجود مسبقاً', 'danger')
        conn.close()
        return redirect(url_for('users.users'))
    return render_template('add_user.html')


@users_bp.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    if session['user_role'] != 'مدير':
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('users.users'))
    if user_id == session['user_id']:
        flash('❌ لا يمكنك حذف حسابك الخاص', 'danger')
        return redirect(url_for('users.users'))
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('❌ المستخدم غير موجود', 'danger')
        conn.close()
        return redirect(url_for('users.users'))
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('✅ تم حذف المستخدم بنجاح', 'success')
    log_activity(session['user_id'], 'حذف مستخدم', f'حذف {user["username"]}')
    return redirect(url_for('users.users'))


# ===== إدارة صلاحيات المستخدم =====
@users_bp.route('/user_permissions/<int:user_id>')
def user_permissions(user_id):
    """عرض صلاحيات المستخدم"""
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('❌ المستخدم غير موجود', 'danger')
        conn.close()
        return redirect(url_for('users.user_permissions', user_id=user_id))
    
    # جلب جميع الصلاحيات
    all_permissions = conn.execute('SELECT * FROM permissions ORDER BY resource, action').fetchall()
    
    # جلب صلاحيات المستخدم الكلية (من الدور + الإضافية)
    user_perms = get_user_permissions(user_id)
    
    # جلب صلاحيات الدور فقط (باستخدام role النصي)
    role_perms = set()
    cursor = conn.execute("""
        SELECT p.name 
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN roles r ON r.id = rp.role_id
        JOIN users u ON u.role = r.name
        WHERE u.id = ?
    """, (user_id,))
    for row in cursor.fetchall():
        role_perms.add(row[0])
    
    # جلب الصلاحيات الإضافية فقط (من user_permissions)
    extra_perms = set()
    cursor = conn.execute("""
        SELECT p.name 
        FROM permissions p
        JOIN user_permissions up ON p.id = up.permission_id
        WHERE up.user_id = ?
    """, (user_id,))
    for row in cursor.fetchall():
        extra_perms.add(row[0])
    
    conn.close()
    
    # تنظيم الصلاحيات حسب المصدر
    grouped_permissions = {}
    for perm in all_permissions:
        resource = perm['resource']
        if resource not in grouped_permissions:
            grouped_permissions[resource] = []
        
        is_role = perm['name'] in role_perms
        is_extra = perm['name'] in extra_perms
        is_active = perm['name'] in user_perms
        
        grouped_permissions[resource].append({
            'id': perm['id'],
            'name': perm['name'],
            'action': perm['action'],
            'description': perm['description'],
            'has_permission': is_active,
            'from_role': is_role,
            'from_extra': is_extra
        })
    
    return render_template('user_permissions.html', 
                         user=user, 
                         grouped_permissions=grouped_permissions)


@users_bp.route('/toggle_permission/<int:user_id>/<int:permission_id>', methods=['POST'])
def toggle_permission(user_id, permission_id):
    """تفعيل/إلغاء صلاحية للمستخدم"""
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db()
    permission = conn.execute('SELECT name FROM permissions WHERE id = ?', (permission_id,)).fetchone()
    if not permission:
        flash('❌ الصلاحية غير موجودة', 'danger')
        conn.close()
        return redirect(url_for('users.user_permissions', user_id=user_id))
    
    # التحقق من وجود الصلاحية
    if has_permission(user_id, permission['name']):
        remove_permission_from_user(user_id, permission['name'])
        flash('✅ تم إلغاء الصلاحية', 'success')
    else:
        add_permission_to_user(user_id, permission['name'])
        flash('✅ تم إضافة الصلاحية', 'success')
    
    conn.close()
    return redirect(url_for('users.user_permissions', user_id=user_id))