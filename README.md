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
   # Desktop app
   python app.py

# Or run the Flask web app (suitable for Render deployment)
```
python web_app.py
```
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
To deploy on Render (or similar):

1. Ensure `requirements.txt` contains `gunicorn` and `Flask` (already included).
2. Push the repo to GitHub.
3. Create a new Web service on Render, connect your GitHub repo, and set the start command to:

```
gunicorn web_app:app
```

4. Add environment variables for your MySQL connection and `FLASK_SECRET`.

