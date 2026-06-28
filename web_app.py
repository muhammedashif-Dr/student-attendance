from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, flash
import os
import csv
import io
import hashlib
from datetime import datetime
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET', 'change-me')

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "student_attendance"),
}

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


def connect(use_database: bool = True):
    cfg = dict(DB_CONFIG)
    if not use_database:
        cfg.pop('database', None)
    return mysql.connector.connect(**cfg, autocommit=True)


def initialize_database():
    try:
        conn = connect(use_database=False)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}`")
        cursor.close()
        conn.close()

        conn = connect(use_database=True)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                student_id VARCHAR(20) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                department VARCHAR(100),
                class_name VARCHAR(50),
                phone VARCHAR(20),
                password VARCHAR(100) DEFAULT ''
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id VARCHAR(20) NOT NULL,
                attendance_date DATE NOT NULL,
                status VARCHAR(10) NOT NULL,
                UNIQUE KEY uq_student_date (student_id, attendance_date),
                FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
            )
            """
        )
        cursor.close()
        conn.close()
    except Error as e:
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

        # admin
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['role'] = 'admin'
            session['name'] = 'Administrator'
            return redirect(url_for('admin_dashboard'))

        try:
            conn = connect()
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT student_id, name, password FROM students WHERE student_id = %s', (username,))
            student = cursor.fetchone()
            cursor.close()
            conn.close()
            if student and (student['password'] == hash_password(password) or student['password'] == password):
                session['role'] = 'student'
                session['student_id'] = student['student_id']
                session['name'] = student['name']
                return redirect(url_for('student_dashboard'))
            flash('Invalid credentials', 'danger')
        except Error as e:
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
        cursor.execute('SELECT COUNT(*), SUM(CASE WHEN status = "Present" THEN 1 ELSE 0 END) FROM attendance WHERE student_id = %s', (student_id,))
        totals = cursor.fetchone()
        cursor.execute('SELECT attendance_date, status FROM attendance WHERE student_id = %s ORDER BY attendance_date DESC LIMIT 100', (student_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        total_days = totals[0] or 0
        present = totals[1] or 0
        percentage = round((present / total_days) * 100, 2) if total_days else 0
    except Error as e:
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
            pat = f"%{term}%"
            cursor.execute('''SELECT student_id, name, department, class_name, phone FROM students WHERE student_id LIKE %s OR name LIKE %s OR department LIKE %s OR class_name LIKE %s OR phone LIKE %s ORDER BY name''', (pat, pat, pat, pat, pat))
        else:
            cursor.execute('SELECT student_id, name, department, class_name, phone FROM students ORDER BY name')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        data = [dict(student_id=r[0], name=r[1], department=r[2], class_name=r[3], phone=r[4]) for r in rows]
        return jsonify(data)
    except Error as e:
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
        cursor.execute('''INSERT INTO students (student_id, name, department, class_name, phone, password) VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE name=VALUES(name), department=VALUES(department), class_name=VALUES(class_name), phone=VALUES(phone), password=VALUES(password)''', (student_id, name, dept, cls, phone, hashed))
        cursor.close()
        conn.close()
        return jsonify({'ok': True})
    except Error as e:
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
        cursor.execute('''INSERT INTO attendance (student_id, attendance_date, status) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE status=VALUES(status)''', (student_id, date, status))
        cursor.close()
        conn.close()
        return jsonify({'ok': True})
    except Error as e:
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
    except Error as e:
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
        writer.writerow(["Student ID", "Name", "Total Days", "Present", "Absent", "Attendance %"])
        for student_id, name, total_days, present_days, absent_days in rows:
            total_days = total_days or 0
            present_days = present_days or 0
            absent_days = absent_days or 0
            percentage = round((present_days / total_days) * 100, 2) if total_days else 0.0
            writer.writerow([student_id, name, total_days, present_days, absent_days, f"{percentage}%"])
        output.seek(0)
        return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='attendance_report.csv')
    except Error as e:
        flash(str(e), 'danger')
        return redirect(url_for('reports'))


if __name__ == '__main__':
    initialize_database()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
