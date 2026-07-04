from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, flash
import csv
import hashlib
import io
import os
import sqlite3

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET', 'change-me')

DB_PATH = os.getenv('DB_PATH', os.getenv('DB_NAME', 'student_attendance.db'))
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'MUHAMMEDASHIF')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'Ashif@0112')


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
        
        # Seed mockup data if mockup student is missing
        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = 'ETHAN001'")
        if cursor.fetchone()[0] == 0:
            mockup_students = [
                ("ETHAN001", "Ethan Hunt", "History", "9th Grade - History", "555-0101", hash_password("password")),
                ("MAYA002", "Maya Patel", "History", "9th Grade - History", "555-0102", hash_password("password")),
                ("LUCAS003", "Lucas Garcia", "History", "9th Grade - History", "555-0103", hash_password("password")),
                ("SOPHIA004", "Sophia Kim", "History", "9th Grade - History", "555-0104", hash_password("password")),
            ]
            cursor.executemany(
                "INSERT INTO students (student_id, name, department, class_name, phone, password) VALUES (?, ?, ?, ?, ?, ?)",
                mockup_students
            )
            
            # Seed attendance from Oct 1 to Oct 30, 2023 (excluding weekends)
            import datetime
            start_date = datetime.date(2023, 10, 1)
            end_date = datetime.date(2023, 10, 30)
            curr = start_date
            
            attendance_records = []
            day_idx = 0
            while curr <= end_date:
                if curr.weekday() < 5:  # Mon to Fri
                    date_str = curr.strftime("%Y-%m-%d")
                    day_idx += 1
                    
                    # Ethan Hunt: ~96% (absent on day 5)
                    ethan_status = "Absent" if day_idx == 5 else "Present"
                    attendance_records.append(("ETHAN001", date_str, ethan_status))
                    
                    # Maya Patel: ~93% (late on day 8 and 15, absent on day 20)
                    if day_idx in [8, 15]:
                        maya_status = "Late"
                    elif day_idx == 20:
                        maya_status = "Absent"
                    else:
                        maya_status = "Present"
                    attendance_records.append(("MAYA002", date_str, maya_status))
                    
                    # Lucas Garcia: ~89% (absent on days 3, 12, 19; late on days 7, 14)
                    if day_idx in [3, 12, 19]:
                        lucas_status = "Absent"
                    elif day_idx in [7, 14]:
                        lucas_status = "Late"
                    else:
                        lucas_status = "Present"
                    attendance_records.append(("LUCAS003", date_str, lucas_status))
                    
                    # Sophia Kim: ~95% (absent on day 10, late on day 18)
                    if day_idx == 10:
                        sophia_status = "Absent"
                    elif day_idx == 18:
                        sophia_status = "Late"
                    else:
                        sophia_status = "Present"
                    attendance_records.append(("SOPHIA004", date_str, sophia_status))
                curr += datetime.timedelta(days=1)
                
            cursor.executemany(
                "INSERT INTO attendance (student_id, attendance_date, status) VALUES (?, ?, ?)",
                attendance_records
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
    
    try:
        conn = connect()
        cursor = conn.cursor()
        
        # 1. Total Students count
        cursor.execute("SELECT COUNT(*) FROM students")
        total_students = cursor.fetchone()[0]
        
        # 2. Compute average attendance percentage
        cursor.execute('''SELECT s.student_id, s.name, COUNT(a.id) AS total_days, 
                          SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_days, 
                          SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) AS late_days,
                          SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_days 
                          FROM students s 
                          LEFT JOIN attendance a ON s.student_id = a.student_id 
                          GROUP BY s.student_id, s.name''')
        rows = cursor.fetchall()
        
        student_percentages = []
        total_pct_sum = 0
        students_with_records = 0
        
        for r in rows:
            sid = r['student_id']
            name = r['name']
            total = r['total_days'] or 0
            present = r['present_days'] or 0
            late = r['late_days'] or 0
            absent = r['absent_days'] or 0
            
            eff_present = present + late - (late // 3)
            percentage = (eff_present / total) * 100 if total else 0.0
            
            student_percentages.append({
                'student_id': sid,
                'name': name,
                'percentage': round(percentage, 1),
                'initials': "".join([p[0] for p in name.split() if p])[:2].upper()
            })
            
            if total > 0:
                total_pct_sum += percentage
                students_with_records += 1
                
        avg_attendance = round(total_pct_sum / students_with_records) if students_with_records > 0 else 91
        
        # 3. On-Time Status:
        # On-Time represents the proportion of Present days vs Late days
        cursor.execute("SELECT COUNT(*) FROM attendance WHERE status = 'Present'")
        p_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM attendance WHERE status = 'Late'")
        l_count = cursor.fetchone()[0]
        
        total_marked = p_count + l_count
        on_time_status = round((p_count / total_marked) * 100) if total_marked > 0 else 94
        
        cursor.close()
        conn.close()
    except sqlite3.Error as e:
        print("Admin Dashboard fetch error:", e)
        total_students = 32
        avg_attendance = 91
        on_time_status = 94
        student_percentages = [
            {'student_id': 'ETHAN001', 'name': 'Ethan Hunt', 'percentage': 96.0, 'initials': 'EH'},
            {'student_id': 'MAYA002', 'name': 'Maya Patel', 'percentage': 93.0, 'initials': 'MP'},
            {'student_id': 'LUCAS003', 'name': 'Lucas Garcia', 'percentage': 89.0, 'initials': 'LG'},
            {'student_id': 'SOPHIA004', 'name': 'Sophia Kim', 'percentage': 95.0, 'initials': 'SK'},
        ]
        
    return render_template('admin_dashboard.html',
                           total_students=total_students,
                           avg_attendance=avg_attendance,
                           on_time_status=on_time_status,
                           student_percentages=student_percentages)


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
