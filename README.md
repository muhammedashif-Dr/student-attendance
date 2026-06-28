# Student Attendance Management System

A polished desktop attendance management application built with Python, MySQL, and Tkinter.

## New Features
- Modern login screen with Administrator and Student roles
- Admin dashboard for registering students, marking attendance, and exporting reports
- Student view for checking personal attendance summary and history
- Stylish card-based interface with a cleaner, interactive UI

## Features
- Register students
- Mark daily attendance as Present/Absent
- View attendance percentages for each student
- Export attendance reports to CSV

## Requirements
- Python 3.9+
- MySQL Server
- `pip install -r requirements.txt`

## Default Login
- Administrator: `admin` / `admin123`
- Student: use your student ID and a password set during registration

## Database Setup
1. Start your MySQL server.
2. Create a database user and update the connection settings in `app.py` if needed.
3. Run the SQL script:
   ```bash
   mysql -u <username> -p < schema.sql
   ```
4. Start the app:
   ```bash
   python app.py
   ```

## Notes
The app uses the following MySQL database configuration by default:
- Host: `localhost`
- Port: `3306`
- Database: `student_attendance`
- User: `root`

You can override these values with environment variables:
- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
