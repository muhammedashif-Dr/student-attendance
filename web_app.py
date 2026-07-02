from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, flash
import csv
import hashlib
import io
import os
import sqlite3

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET', 'change-me')

DB_PATH = os.getenv('DB_PATH', os.getenv('DB_NAME', 'student_attendance.db'))
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')


def connect():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def initialize_database():
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT,
                class_name TEXT,
                phone TEXT,
                password TEXT DEFAULT ''
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                attendance_date TEXT NOT NULL,
                status TEXT NOT NULL,
                UNIQUE(student_id, attendance_date),
                FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()
        cursor.close()
        conn.close()
    except sqlite3.Error as e:
        print('Database init error:', e)


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('Provide username and password', 'warning')
            return redirect(url_for('login'))

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['role'] = 'admin'
            session['name'] = 'Administrator'
            return redirect(url_for('admin_dashboard'))

        try:
            conn = connect()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id, name, password FROM students WHERE student_id = ?', (username,))
            student = cursor.fetchone()
            cursor.close()
            conn.close()
            if student and (student['password'] == hash_password(password) or student['password'] == password):
                session['role'] = 'student'
                session['student_id'] = student['student_id']
                session['name'] = student['name']
                return redirect(url_for('student_dashboard'))
            flash('Invalid credentials', 'danger')
        except sqlite3.Error as e:
            flash(str(e), 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')


@app.route('/student')
def student_dashboard():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    student_id = session.get('student_id')
    try:
        conn = connect()
        cursor = conn.cursor()
        
        # Get count of Present, Late, Absent
        cursor.execute('''SELECT COUNT(*), 
                          SUM(CASE WHEN status = "Present" THEN 1 ELSE 0 END) AS present_days,
                          SUM(CASE WHEN status = "Late" THEN 1 ELSE 0 END) AS late_days,
                          SUM(CASE WHEN status = "Absent" THEN 1 ELSE 0 END) AS absent_days
                          FROM attendance WHERE student_id = ?''', (student_id,))
        totals = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        total_days = totals[0] or 0
        present = totals[1] or 0
        late = totals[2] or 0
        absent = totals[3] or 0
        
        # Apply 3 lates = 1 absent
        eff_present = present + late - (late // 3)
        eff_absent = absent + (late // 3)
        
        percentage = round((eff_present / total_days) * 100, 2) if total_days else 0
        
        # Pre-process rows to display dynamic 3rd late in history
        processed_rows = []
        conn = connect()
        cursor = conn.cursor()
        cursor.execute('SELECT attendance_date, status FROM attendance WHERE student_id = ? ORDER BY attendance_date ASC', (student_id,))
        all_rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        late_count = 0
        chrono_processed = []
        for r in all_rows:
            date_str = r['attendance_date']
            status = r['status']
            disp_status = status
            if status == 'Late':
                late_count += 1
                if late_count % 3 == 0:
                    disp_status = 'Absent (3rd Late)'
            chrono_processed.append((date_str, disp_status))
            
        processed_rows = list(reversed(chrono_processed))[:100]
        
    except sqlite3.Error as e:
        flash(str(e), 'danger')
        processed_rows = []
        total_days = present = late = absent = eff_present = eff_absent = percentage = 0
        
    return render_template('student_dashboard.html', 
                           rows=processed_rows, 
                           total_days=total_days, 
                           present=present, 
                           late=late,
                           absent=absent,
                           eff_present=eff_present,
                           eff_absent=eff_absent,
                           percentage=percentage)


@app.route('/api/students', methods=['GET', 'POST'])
def api_students():
    if session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    term = request.args.get('q', '').strip()
    try:
        conn = connect()
        cursor = conn.cursor()
        if term:
            pat = f'%{term}%'
            cursor.execute('''SELECT student_id, name, department, class_name, phone FROM students WHERE student_id LIKE ? OR name LIKE ? OR department LIKE ? OR class_name LIKE ? OR phone LIKE ? ORDER BY name''', (pat, pat, pat, pat, pat))
        else:
            cursor.execute('SELECT student_id, name, department, class_name, phone FROM students ORDER BY name')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        data = [dict(student_id=r['student_id'], name=r['name'], department=r['department'], class_name=r['class_name'], phone=r['phone']) for r in rows]
        return jsonify(data)
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/student', methods=['POST'])
def api_save_student():
    if session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    payload = request.form
    student_id = payload.get('student_id', '').strip()
    name = payload.get('name', '').strip()
    dept = payload.get('department', '').strip()
    cls = payload.get('class_name', '').strip()
    phone = payload.get('phone', '').strip()
    pwd = payload.get('password', '').strip() or student_id
    if not student_id or not name:
        return jsonify({'error': 'student_id and name required'}), 400
    try:
        conn = connect()
        cursor = conn.cursor()
        hashed = hash_password(pwd)
        cursor.execute('''INSERT INTO students (student_id, name, department, class_name, phone, password) VALUES (?,?,?,?,?,?) ON CONFLICT(student_id) DO UPDATE SET name=excluded.name, department=excluded.department, class_name=excluded.class_name, phone=excluded.phone, password=excluded.password''', (student_id, name, dept, cls, phone, hashed))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True})
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500


def get_late_count(student_id, date=None):
    try:
        conn = connect()
        cursor = conn.cursor()
        if date:
            cursor.execute('SELECT COUNT(*) FROM attendance WHERE student_id = ? AND status = "Late" AND attendance_date != ?', (student_id, date))
        else:
            cursor.execute('SELECT COUNT(*) FROM attendance WHERE student_id = ? AND status = "Late"', (student_id,))
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except sqlite3.Error:
        return 0


@app.route('/api/attendance-by-date', methods=['GET'])
def api_attendance_by_date():
    if session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    date = request.args.get('date', '').strip()
    if not date:
        return jsonify({'error': 'date is required'}), 400
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute('SELECT student_id, name, department, class_name FROM students ORDER BY name')
        students = cursor.fetchall()
        
        cursor.execute('SELECT student_id, status FROM attendance WHERE attendance_date = ?', (date,))
        attendance_map = {r['student_id']: r['status'] for r in cursor.fetchall()}
        
        cursor.close()
        conn.close()
        
        data = []
        for s in students:
            sid = s['student_id']
            prev_lates = get_late_count(sid, date=date)
            status = attendance_map.get(sid, 'Present')
            
            data.append({
                'student_id': sid,
                'name': s['name'],
                'department': s['department'],
                'class_name': s['class_name'],
                'status': status,
                'prev_lates': prev_lates
            })
            
        return jsonify(data)
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/attendance', methods=['POST'])
def api_mark_attendance():
    if session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    payload = request.form
    student_id = payload.get('student_id')
    date = payload.get('date')
    status = payload.get('status')
    if not student_id or not date or not status:
        return jsonify({'error': 'missing fields'}), 400
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO attendance (student_id, attendance_date, status) VALUES (?,?,?) ON CONFLICT(student_id, attendance_date) DO UPDATE SET status=excluded.status''', (student_id, date, status))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True})
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500


@app.route('/reports')
def reports():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute('''SELECT s.student_id, s.name, COUNT(a.id) AS total_days, 
                          SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_days, 
                          SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) AS late_days,
                          SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_days 
                          FROM students s 
                          LEFT JOIN attendance a ON s.student_id = a.student_id 
                          GROUP BY s.student_id, s.name 
                          ORDER BY s.name''')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        processed_rows = []
        for r in rows:
            sid = r['student_id']
            name = r['name']
            total = r['total_days'] or 0
            present = r['present_days'] or 0
            late = r['late_days'] or 0
            absent = r['absent_days'] or 0
            
            eff_present = present + late - (late // 3)
            eff_absent = absent + (late // 3)
            percentage = round((eff_present / total) * 100, 2) if total else 0.0
            
            processed_rows.append((sid, name, total, present, late, absent, eff_present, eff_absent, percentage))
            
    except sqlite3.Error as e:
        flash(str(e), 'danger')
        processed_rows = []
    return render_template('reports.html', rows=processed_rows)


@app.route('/export_csv')
def export_csv():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute('''SELECT s.student_id, s.name, COUNT(a.id) AS total_days, 
                          SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_days, 
                          SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) AS late_days,
                          SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_days 
                          FROM students s 
                          LEFT JOIN attendance a ON s.student_id = a.student_id 
                          GROUP BY s.student_id, s.name 
                          ORDER BY s.name''')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Student ID', 'Name', 'Total Days', 'Present', 'Late', 'Absent', 'Effective Present', 'Effective Absent', 'Attendance %'])
        for r in rows:
            sid = r['student_id']
            name = r['name']
            total = r['total_days'] or 0
            present = r['present_days'] or 0
            late = r['late_days'] or 0
            absent = r['absent_days'] or 0
            
            eff_present = present + late - (late // 3)
            eff_absent = absent + (late // 3)
            percentage = round((eff_present / total) * 100, 2) if total else 0.0
            writer.writerow([sid, name, total, present, late, absent, eff_present, eff_absent, f'{percentage}%'])
        output.seek(0)
        return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='attendance_report.csv')
    except sqlite3.Error as e:
        flash(str(e), 'danger')
        return redirect(url_for('reports'))


initialize_database()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
