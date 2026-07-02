# Student Attendance Management System

A polished attendance management application built with Python, Flask, and SQLite.

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
- `pip install -r requirements.txt`

## Default Login
- Administrator: `MUHAMMEDASHIF` / `Ashif@0112`
- Student: use your student ID and a password set during registration

## Database
This project uses SQLite for data storage. The app will create the database file and tables on first run.

The default database file is `student_attendance.db`.

Start the app:
```bash
# Desktop app
python app_desktop.py

# Or run the Flask web app (suitable for Render deployment)
python web_app.py
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

Notes about entrypoints
- Desktop app: the desktop Tkinter application was renamed to `app_desktop.py` to avoid being imported by web servers. Run locally with:

```
python app_desktop.py
```

- Web app (Render): ensure your Render start command or service uses the following command so it runs the Flask web app and does not import any Tkinter UI:

```
gunicorn web_app:app
```

