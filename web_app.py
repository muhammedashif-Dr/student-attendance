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
        cursor.execute('SELECT COUNT(*), SUM(CASE WHEN status = "Present" THEN 1 ELSE 0 END) FROM attendance WHERE student_id = ?', (student_id,))
        totals = cursor.fetchone()
        cursor.execute('SELECT attendance_date, status FROM attendance WHERE student_id = ? ORDER BY attendance_date DESC LIMIT 100', (student_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        total_days = totals[0] or 0
        present = totals[1] or 0
        percentage = round((present / total_days) * 100, 2) if total_days else 0
    except sqlite3.Error as e:
        flash(str(e), 'danger')
        rows = []
        total_days = present = percentage = 0
    return render_template('student_dashboard.html', rows=rows, total_days=total_days, present=present, percentage=percentage)


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
        cursor.execute('''SELECT s.student_id, s.name, COUNT(a.id) AS total_days, SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_days, SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_days FROM students s LEFT JOIN attendance a ON s.student_id = a.student_id GROUP BY s.student_id, s.name ORDER BY s.name''')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
    except sqlite3.Error as e:
        flash(str(e), 'danger')
        rows = []
    return render_template('reports.html', rows=rows)


@app.route('/export_csv')
def export_csv():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute('''SELECT s.student_id, s.name, COUNT(a.id) AS total_days, SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_days, SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_days FROM students s LEFT JOIN attendance a ON s.student_id = a.student_id GROUP BY s.student_id, s.name ORDER BY s.name''')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Student ID', 'Name', 'Total Days', 'Present', 'Absent', 'Attendance %'])
        for student_id, name, total_days, present_days, absent_days in rows:
            total_days = total_days or 0
            present_days = present_days or 0
            absent_days = absent_days or 0
            percentage = round((present_days / total_days) * 100, 2) if total_days else 0.0
            writer.writerow([student_id, name, total_days, present_days, absent_days, f'{percentage}%'])
        output.seek(0)
        return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='attendance_report.csv')
    except sqlite3.Error as e:
        flash(str(e), 'danger')
        return redirect(url_for('reports'))


initialize_database()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
