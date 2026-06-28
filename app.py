import csv
import hashlib
import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import mysql.connector
from mysql.connector import Error


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "student_attendance"),
}

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

BG = "#f3f7ff"
CARD = "#ffffff"
PRIMARY = "#4f46e5"
PRIMARY_DARK = "#3730a3"
ACCENT = "#14b8a6"
TEXT = "#172033"
MUTED = "#64748b"
DANGER = "#ef4444"
SUCCESS = "#22c55e"


class AttendanceApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Smart Attendance Hub")
        self.root.geometry("1220x780")
        self.root.minsize(1040, 720)
        self.root.configure(bg=BG)

        self.student_id_map = {}
        self.report_rows = []
        self.current_role = None
        self.current_student_id = None
        self.current_student_name = None
        self.editing_student_id = None

        self._setup_styles()
        self.initialize_database()
        self._build_login_screen()

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Card.TFrame", background=CARD)
        style.configure("Page.TFrame", background=BG)
        style.configure("Sidebar.TFrame", background="#eef2ff")
        style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 24, "bold"))
        style.configure("Subtitle.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 11))
        style.configure("Label.TLabel", background=CARD, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Accent.TButton", background=PRIMARY, foreground="white", font=("Segoe UI", 10, "bold"))
        style.map(
            "Accent.TButton",
            background=[("active", PRIMARY_DARK), ("pressed", PRIMARY_DARK)],
            foreground=[("active", "white"), ("pressed", "white")],
        )
        style.configure("Secondary.TButton", background="#e2e8f0", foreground=TEXT, font=("Segoe UI", 10, "bold"))
        style.map("Secondary.TButton", background=[("active", "#cbd5e1"), ("pressed", "#cbd5e1")])
        style.configure("Role.TButton", background="#e2e8f0", foreground=TEXT, font=("Segoe UI", 10, "bold"))
        style.map("Role.TButton", background=[("active", "#dbeafe"), ("pressed", "#dbeafe")])

    def _build_login_screen(self) -> None:
        self.login_frame = tk.Frame(self.root, bg=BG)
        self.login_frame.pack(fill="both", expand=True)

        wrapper = tk.Frame(self.login_frame, bg=BG)
        wrapper.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(wrapper, bg=CARD, bd=0, highlightthickness=1, highlightbackground="#e2e8f0")
        card.grid(row=0, column=0, padx=24, pady=24)

        inner = tk.Frame(card, bg=CARD, width=420, height=420)
        inner.grid(row=0, column=0)
        inner.grid_propagate(False)
        inner.columnconfigure(0, weight=1)

        tk.Label(inner, text="Welcome", bg=CARD, fg=TEXT, font=("Segoe UI", 22, "bold")).grid(row=0, column=0, sticky="w", padx=28, pady=(28, 6))
        tk.Label(inner, text="Sign in to access the attendance system", bg=CARD, fg=MUTED, font=("Segoe UI", 11)).grid(row=1, column=0, sticky="w", padx=28, pady=(0, 20))

        self.form_frame = tk.Frame(inner, bg=CARD)
        self.form_frame.grid(row=2, column=0, sticky="ew", padx=28)
        self.form_frame.columnconfigure(0, weight=1)

        tk.Label(self.form_frame, text="Username", bg=CARD, fg=TEXT, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(self.form_frame, textvariable=self.username_var, width=40)
        self.username_entry.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        tk.Label(self.form_frame, text="Password", bg=CARD, fg=TEXT, font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=(0, 6))
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(self.form_frame, textvariable=self.password_var, width=40, show="*")
        self.password_entry.grid(row=3, column=0, sticky="ew", pady=(0, 18))

        self.login_button = tk.Button(
            self.form_frame,
            text="Sign In",
            bg=PRIMARY,
            fg="white",
            relief="flat",
            bd=0,
            padx=14,
            pady=10,
            activebackground=PRIMARY_DARK,
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            command=self.handle_login,
        )
        self.login_button.grid(row=4, column=0, sticky="ew")
        self.username_entry.focus_set()

    def _build_main_ui(self) -> None:
        self.login_frame.destroy()
        self.main_frame = tk.Frame(self.root, bg=BG)
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(1, weight=1)

        sidebar = tk.Frame(self.main_frame, bg="#eef2ff", width=250)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")
        sidebar.grid_propagate(False)

        title = tk.Label(sidebar, text="Smart Attendance", bg="#eef2ff", fg=PRIMARY_DARK, font=("Segoe UI", 20, "bold"), anchor="w")
        title.pack(anchor="w", padx=20, pady=(24, 10))
        tk.Label(sidebar, text="Campus management portal", bg="#eef2ff", fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=(0, 24))

        if self.current_role == "Administrator":
            tk.Label(sidebar, text="ADMIN PANEL", bg="#eef2ff", fg=PRIMARY, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20, pady=(0, 8))
        else:
            tk.Label(sidebar, text="STUDENT PANEL", bg="#eef2ff", fg=ACCENT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20, pady=(0, 8))

        self.header_frame = tk.Frame(self.main_frame, bg=BG)
        self.header_frame.grid(row=0, column=1, sticky="ew", padx=(20, 20), pady=(20, 10))
        self.header_frame.columnconfigure(0, weight=1)
        tk.Label(self.header_frame, text="Attendance Management System", bg=BG, fg=TEXT, font=("Segoe UI", 22, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(self.header_frame, text=f"Signed in as {self.current_role.lower()} • {self.current_student_name or 'admin'}", bg=BG, fg=MUTED, font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=(2, 0))
        logout_btn = tk.Button(self.header_frame, text="Logout", bg="#fee2e2", fg=DANGER, relief="flat", bd=0, padx=12, pady=8, font=("Segoe UI", 10, "bold"), command=self.logout)
        logout_btn.grid(row=0, column=1, rowspan=2, sticky="e")

        content = tk.Frame(self.main_frame, bg=BG)
        content.grid(row=1, column=1, sticky="nsew", padx=(20, 20), pady=(0, 20))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        if self.current_role == "Administrator":
            self._build_admin_dashboard(content)
        else:
            self._build_student_dashboard(content)

    def _build_admin_dashboard(self, parent: tk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.grid(row=0, column=0, sticky="nsew")

        self._build_dashboard_tab(notebook)
        self._build_registration_tab(notebook)
        self._build_attendance_tab(notebook)
        self._build_reports_tab(notebook)

        self.load_students()
        self.refresh_student_selector()
        self.refresh_reports()

    def _build_student_dashboard(self, parent: tk.Frame) -> None:
        card = tk.Frame(parent, bg=CARD, bd=0, highlightthickness=1, highlightbackground="#e2e8f0")
        card.pack(fill="both", expand=True)

        hero = tk.Frame(card, bg=PRIMARY)
        hero.pack(fill="x")
        tk.Label(hero, text=f"Hello {self.current_student_name}", bg=PRIMARY, fg="white", font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=24, pady=(20, 6))
        tk.Label(hero, text="Here is your attendance summary and recent activity.", bg=PRIMARY, fg="#e0e7ff", font=("Segoe UI", 11)).pack(anchor="w", padx=24, pady=(0, 20))

        summary_frame = tk.Frame(card, bg=CARD)
        summary_frame.pack(fill="x", padx=24, pady=20)
        summary_frame.columnconfigure(0, weight=1)
        summary_frame.columnconfigure(1, weight=1)
        summary_frame.columnconfigure(2, weight=1)

        self.student_total_var = tk.StringVar(value="0")
        self.student_present_var = tk.StringVar(value="0")
        self.student_percentage_var = tk.StringVar(value="0%")
        self._create_stat_card(summary_frame, "Total Days", self.student_total_var, 0, 0)
        self._create_stat_card(summary_frame, "Present", self.student_present_var, 1, 0)
        self._create_stat_card(summary_frame, "Attendance %", self.student_percentage_var, 2, 0)

        tree_frame = tk.Frame(card, bg=CARD)
        tree_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        ttk.Label(tree_frame, text="Attendance History", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.student_history_tree = ttk.Treeview(tree_frame, columns=("date", "status"), show="headings")
        self.student_history_tree.heading("date", text="Date")
        self.student_history_tree.heading("status", text="Status")
        self.student_history_tree.column("date", width=180)
        self.student_history_tree.column("status", width=120)
        self.student_history_tree.grid(row=1, column=0, sticky="nsew")
        tree_frame.rowconfigure(1, weight=1)
        self.load_student_view()

    def _create_stat_card(self, parent: tk.Frame, label: str, variable: tk.StringVar, col: int, row: int) -> None:
        panel = tk.Frame(parent, bg="#f8fafc", bd=0, highlightthickness=1, highlightbackground="#e2e8f0")
        panel.grid(row=row, column=col, padx=8, sticky="nsew")
        tk.Label(panel, text=label, bg="#f8fafc", fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=14, pady=(12, 4))
        tk.Label(panel, textvariable=variable, bg="#f8fafc", fg=TEXT, font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=14, pady=(0, 12))

    def _build_dashboard_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=16, style="Page.TFrame")
        notebook.add(frame, text="Dashboard")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)

        self.total_students_var = tk.StringVar(value="0")
        self.present_var = tk.StringVar(value="0")
        self.avg_var = tk.StringVar(value="0%")
        self._create_stat_card(frame, "Students", self.total_students_var, 0, 0)
        self._create_stat_card(frame, "Present Today", self.present_var, 1, 0)
        self._create_stat_card(frame, "Average Attendance", self.avg_var, 2, 0)

        activity_frame = tk.Frame(frame, bg=CARD, bd=0, highlightthickness=1, highlightbackground="#e2e8f0")
        activity_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(16, 0))
        activity_frame.columnconfigure(0, weight=1)
        activity_frame.rowconfigure(0, weight=1)
        tk.Label(activity_frame, text="Latest Attendance Activity", bg=CARD, fg=TEXT, font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        self.activity_tree = ttk.Treeview(activity_frame, columns=("student", "date", "status"), show="headings")
        self.activity_tree.heading("student", text="Student")
        self.activity_tree.heading("date", text="Date")
        self.activity_tree.heading("status", text="Status")
        self.activity_tree.column("student", width=220)
        self.activity_tree.column("date", width=180)
        self.activity_tree.column("status", width=120)
        self.activity_tree.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        activity_frame.rowconfigure(1, weight=1)

    def _build_registration_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=16, style="Page.TFrame")
        notebook.add(frame, text="Student Registration")
        frame.columnconfigure(1, weight=1)

        self.student_search_var = tk.StringVar()
        search_bar = ttk.Frame(frame)
        search_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(search_bar, text="Search Student").pack(side="left", padx=(0, 6))
        ttk.Entry(search_bar, textvariable=self.student_search_var, width=40).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(search_bar, text="Search", command=self.search_students).pack(side="left", padx=2)
        ttk.Button(search_bar, text="Refresh", command=self.load_students).pack(side="left", padx=2)

        ttk.Label(frame, text="Student ID", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", padx=5, pady=6)
        self.student_id_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.student_id_var, width=40).grid(row=1, column=1, sticky="ew", padx=5, pady=6)

        ttk.Label(frame, text="Full Name", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", padx=5, pady=6)
        self.name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.name_var, width=40).grid(row=2, column=1, sticky="ew", padx=5, pady=6)

        ttk.Label(frame, text="Department", font=("Segoe UI", 10, "bold")).grid(row=3, column=0, sticky="w", padx=5, pady=6)
        self.department_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.department_var, width=40).grid(row=3, column=1, sticky="ew", padx=5, pady=6)

        ttk.Label(frame, text="Class", font=("Segoe UI", 10, "bold")).grid(row=4, column=0, sticky="w", padx=5, pady=6)
        self.class_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.class_var, width=40).grid(row=4, column=1, sticky="ew", padx=5, pady=6)

        ttk.Label(frame, text="Phone", font=("Segoe UI", 10, "bold")).grid(row=5, column=0, sticky="w", padx=5, pady=6)
        self.phone_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.phone_var, width=40).grid(row=5, column=1, sticky="ew", padx=5, pady=6)

        ttk.Label(frame, text="Login Password", font=("Segoe UI", 10, "bold")).grid(row=6, column=0, sticky="w", padx=5, pady=6)
        self.password_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.password_var, width=40, show="*").grid(row=6, column=1, sticky="ew", padx=5, pady=6)

        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Button(buttons, text="Save Student", command=self.save_student).pack(side="left", padx=5)
        ttk.Button(buttons, text="Load Selected", command=self.load_selected_student).pack(side="left", padx=5)
        ttk.Button(buttons, text="Clear", command=self.clear_student_form).pack(side="left", padx=5)

        self.students_tree = ttk.Treeview(frame, columns=("student_id", "name", "department", "class_name", "phone"), show="headings")
        self.students_tree.heading("student_id", text="Student ID")
        self.students_tree.heading("name", text="Name")
        self.students_tree.heading("department", text="Department")
        self.students_tree.heading("class_name", text="Class")
        self.students_tree.heading("phone", text="Phone")
        self.students_tree.column("student_id", width=120)
        self.students_tree.column("name", width=200)
        self.students_tree.column("department", width=180)
        self.students_tree.column("class_name", width=120)
        self.students_tree.column("phone", width=140)
        self.students_tree.grid(row=8, column=0, columnspan=2, sticky="nsew", pady=(14, 0))
        self.students_tree.bind("<Double-1>", self.on_student_select)
        frame.rowconfigure(8, weight=1)

    def _build_attendance_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=16, style="Page.TFrame")
        notebook.add(frame, text="Daily Attendance")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Date", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=8)
        self.attendance_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(frame, textvariable=self.attendance_date_var, width=40).grid(row=0, column=1, sticky="ew", padx=5, pady=8)

        ttk.Label(frame, text="Student", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", padx=5, pady=8)
        self.student_selector_var = tk.StringVar()
        self.student_selector = ttk.Combobox(frame, textvariable=self.student_selector_var, state="readonly", width=40)
        self.student_selector.grid(row=1, column=1, sticky="ew", padx=5, pady=8)

        ttk.Label(frame, text="Status", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", padx=5, pady=8)
        self.status_var = tk.StringVar(value="Present")
        status_frame = ttk.Frame(frame)
        status_frame.grid(row=2, column=1, sticky="w", padx=5, pady=8)
        ttk.Radiobutton(status_frame, text="Present", variable=self.status_var, value="Present").pack(side="left")
        ttk.Radiobutton(status_frame, text="Absent", variable=self.status_var, value="Absent").pack(side="left", padx=10)

        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Button(buttons, text="Mark Attendance", command=self.mark_attendance).pack(side="left", padx=5)
        ttk.Button(buttons, text="Clear", command=self.clear_attendance_form).pack(side="left", padx=5)

    def _build_reports_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=16, style="Page.TFrame")
        notebook.add(frame, text="Reports")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        button_bar = ttk.Frame(frame)
        button_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(button_bar, text="Refresh Report", command=self.refresh_reports).pack(side="left", padx=5)
        ttk.Button(button_bar, text="Export CSV", command=self.export_reports).pack(side="left", padx=5)

        self.report_tree = ttk.Treeview(frame, columns=("student_id", "name", "total_days", "present_days", "absent_days", "percentage"), show="headings")
        self.report_tree.heading("student_id", text="Student ID")
        self.report_tree.heading("name", text="Name")
        self.report_tree.heading("total_days", text="Total Days")
        self.report_tree.heading("present_days", text="Present")
        self.report_tree.heading("absent_days", text="Absent")
        self.report_tree.heading("percentage", text="Attendance %")
        self.report_tree.column("student_id", width=120)
        self.report_tree.column("name", width=220)
        self.report_tree.column("total_days", width=120)
        self.report_tree.column("present_days", width=100)
        self.report_tree.column("absent_days", width=100)
        self.report_tree.column("percentage", width=130)
        self.report_tree.grid(row=1, column=0, sticky="nsew")

    def connect(self, use_database: bool = True):
        config = dict(DB_CONFIG)
        if not use_database:
            config.pop("database", None)
        return mysql.connector.connect(**config, autocommit=True)

    def initialize_database(self) -> None:
        try:
            conn = self.connect(use_database=False)
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}`")
            cursor.close()
            conn.close()

            conn = self.connect(use_database=True)
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
            cursor.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS password VARCHAR(100) DEFAULT ''")
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
        except Error as exc:
            messagebox.showerror("Database Error", f"Unable to connect to MySQL:\n{exc}")
            self.root.destroy()

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def handle_login(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            messagebox.showwarning("Login Required", "Please enter your username and password.")
            return

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            self.current_role = "Administrator"
            self.current_student_name = "Administrator"
            self._build_main_ui()
            return

        try:
            conn = self.connect()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT student_id, name, password FROM students WHERE student_id = %s", (username,))
            student = cursor.fetchone()
            cursor.close()
            conn.close()
            if student and (student["password"] == self._hash_password(password) or student["password"] == password):
                self.current_role = "Student"
                self.current_student_id = student["student_id"]
                self.current_student_name = student["name"]
                self._build_main_ui()
            else:
                messagebox.showerror("Login Failed", "Invalid username or password.")
        except Error as exc:
            messagebox.showerror("Database Error", str(exc))

    def logout(self) -> None:
        self.main_frame.destroy()
        self.current_role = None
        self.current_student_id = None
        self.current_student_name = None
        self._build_login_screen()

    def load_students(self, search_term: str | None = None) -> None:
        try:
            conn = self.connect()
            cursor = conn.cursor()
            term = (search_term if search_term is not None else self.student_search_var.get().strip())
            if term:
                pattern = f"%{term}%"
                cursor.execute(
                    """
                    SELECT student_id, name, department, class_name, phone
                    FROM students
                    WHERE student_id LIKE %s OR name LIKE %s OR department LIKE %s OR class_name LIKE %s OR phone LIKE %s
                    ORDER BY name
                    """,
                    (pattern, pattern, pattern, pattern, pattern),
                )
            else:
                cursor.execute("SELECT student_id, name, department, class_name, phone FROM students ORDER BY name")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            for row in self.students_tree.get_children():
                self.students_tree.delete(row)
            for row in rows:
                self.students_tree.insert("", "end", values=row)
        except Error as exc:
            messagebox.showerror("Database Error", str(exc))

    def search_students(self) -> None:
        self.load_students(self.student_search_var.get().strip())

    def on_student_select(self, event) -> None:
        selection = self.students_tree.selection()
        if not selection:
            return
        values = self.students_tree.item(selection[0], "values")
        if not values:
            return
        self._populate_student_form(values)

    def _populate_student_form(self, values) -> None:
        if len(values) < 5:
            return
        student_id, name, department, class_name, phone = values
        self.student_id_var.set(student_id)
        self.name_var.set(name)
        self.department_var.set(department or "")
        self.class_var.set(class_name or "")
        self.phone_var.set(phone or "")
        self.password_var.set("")
        self.editing_student_id = student_id

    def load_selected_student(self) -> None:
        selection = self.students_tree.selection()
        if not selection:
            messagebox.showinfo("Selection Required", "Select a student from the list first.")
            return
        self._populate_student_form(self.students_tree.item(selection[0], "values"))

    def refresh_student_selector(self) -> None:
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT student_id, name FROM students ORDER BY name")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            self.student_id_map = {}
            display_values = []
            for student_id, name in rows:
                display_value = f"{name} ({student_id})"
                self.student_id_map[display_value] = student_id
                display_values.append(display_value)
            self.student_selector["values"] = display_values
        except Error as exc:
            messagebox.showerror("Database Error", str(exc))

    def save_student(self) -> None:
        student_id = self.student_id_var.get().strip()
        name = self.name_var.get().strip()
        if not student_id or not name:
            messagebox.showwarning("Input Required", "Student ID and Name are required.")
            return

        if self.editing_student_id:
            student_id = self.editing_student_id

        try:
            conn = self.connect()
            cursor = conn.cursor()
            if self.editing_student_id:
                cursor.execute("SELECT password FROM students WHERE student_id = %s", (student_id,))
                existing_password = cursor.fetchone()
                password_value = self.password_var.get().strip()
                if password_value:
                    hashed_password = self._hash_password(password_value)
                else:
                    hashed_password = existing_password[0] if existing_password else self._hash_password(student_id)
                cursor.execute(
                    """
                    UPDATE students
                    SET name = %s,
                        department = %s,
                        class_name = %s,
                        phone = %s,
                        password = %s
                    WHERE student_id = %s
                    """,
                    (name, self.department_var.get().strip(), self.class_var.get().strip(), self.phone_var.get().strip(), hashed_password, student_id),
                )
                message_text = "Student updated successfully."
            else:
                password_value = self.password_var.get().strip() or student_id
                hashed_password = self._hash_password(password_value)
                cursor.execute(
                    """
                    INSERT INTO students (student_id, name, department, class_name, phone, password)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (student_id, name, self.department_var.get().strip(), self.class_var.get().strip(), self.phone_var.get().strip(), hashed_password),
                )
                message_text = "Student saved successfully."
            cursor.close()
            conn.close()
            messagebox.showinfo("Success", message_text)
            self.clear_student_form()
            self.load_students()
            self.refresh_student_selector()
        except Error as exc:
            messagebox.showerror("Database Error", str(exc))

    def clear_student_form(self) -> None:
        self.student_id_var.set("")
        self.name_var.set("")
        self.department_var.set("")
        self.class_var.set("")
        self.phone_var.set("")
        self.password_var.set("")
        self.editing_student_id = None

    def mark_attendance(self) -> None:
        selected_display = self.student_selector_var.get()
        student_id = self.student_id_map.get(selected_display)
        if not student_id:
            messagebox.showwarning("Selection Required", "Please choose a student.")
            return

        attendance_date = self.attendance_date_var.get().strip()
        status = self.status_var.get()
        if not attendance_date:
            messagebox.showwarning("Input Required", "Attendance date is required.")
            return

        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO attendance (student_id, attendance_date, status)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE status = VALUES(status)
                """,
                (student_id, attendance_date, status),
            )
            cursor.close()
            conn.close()
            messagebox.showinfo("Success", f"Attendance marked for {selected_display}.")
            self.clear_attendance_form()
            self.refresh_reports()
            self.refresh_dashboard_metrics()
        except Error as exc:
            messagebox.showerror("Database Error", str(exc))

    def clear_attendance_form(self) -> None:
        self.attendance_date_var.set(datetime.now().strftime("%Y-%m-%d"))
        self.student_selector_var.set("")
        self.status_var.set("Present")

    def refresh_dashboard_metrics(self) -> None:
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM students")
            total_students = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM attendance WHERE attendance_date = %s AND status = 'Present'", (datetime.now().strftime("%Y-%m-%d"),))
            present_today = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM attendance")
            total_attendance = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            self.total_students_var.set(str(total_students))
            self.present_var.set(str(present_today))
            self.avg_var.set(f"{round((present_today / max(total_attendance, 1)) * 100, 1)}%" if total_attendance else "0%")
            self._refresh_activity_tree()
        except Error as exc:
            messagebox.showerror("Database Error", str(exc))

    def _refresh_activity_tree(self) -> None:
        if not hasattr(self, "activity_tree"):
            return
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.name, a.attendance_date, a.status
                FROM attendance a
                JOIN students s ON s.student_id = a.student_id
                ORDER BY a.attendance_date DESC, s.name
                LIMIT 15
                """
            )
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            for row in self.activity_tree.get_children():
                self.activity_tree.delete(row)
            for name, attendance_date, status in rows:
                self.activity_tree.insert("", "end", values=(name, attendance_date, status))
        except Error as exc:
            messagebox.showerror("Database Error", str(exc))

    def refresh_reports(self) -> None:
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    s.student_id,
                    s.name,
                    COUNT(a.id) AS total_days,
                    SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_days,
                    SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_days
                FROM students s
                LEFT JOIN attendance a ON s.student_id = a.student_id
                GROUP BY s.student_id, s.name
                ORDER BY s.name
                """
            )
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            for row in self.report_tree.get_children():
                self.report_tree.delete(row)

            self.report_rows = []
            for student_id, name, total_days, present_days, absent_days in rows:
                total_days = total_days or 0
                present_days = present_days or 0
                absent_days = absent_days or 0
                percentage = round((present_days / total_days) * 100, 2) if total_days else 0.0
                self.report_rows.append((student_id, name, total_days, present_days, absent_days, f"{percentage}%"))
                self.report_tree.insert("", "end", values=(student_id, name, total_days, present_days, absent_days, f"{percentage}%"))
        except Error as exc:
            messagebox.showerror("Database Error", str(exc))

    def load_student_view(self) -> None:
        if self.current_role != "Student" or not self.current_student_id:
            return
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_days,
                    SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present_days
                FROM attendance
                WHERE student_id = %s
                """,
                (self.current_student_id,),
            )
            summary = cursor.fetchone()
            cursor.execute("SELECT attendance_date, status FROM attendance WHERE student_id = %s ORDER BY attendance_date DESC", (self.current_student_id,))
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            total_days = summary[0] or 0
            present_days = summary[1] or 0
            percentage = round((present_days / total_days) * 100, 2) if total_days else 0.0
            self.student_total_var.set(str(total_days))
            self.student_present_var.set(str(present_days))
            self.student_percentage_var.set(f"{percentage}%")

            for row in self.student_history_tree.get_children():
                self.student_history_tree.delete(row)
            for attendance_date, status in rows:
                self.student_history_tree.insert("", "end", values=(attendance_date, status))
        except Error as exc:
            messagebox.showerror("Database Error", str(exc))

    def export_reports(self) -> None:
        if not self.report_rows:
            messagebox.showinfo("No Data", "There is no report data to export.")
            return

        file_path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="attendance_report.csv", filetypes=[("CSV file", "*.csv")])
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(["Student ID", "Name", "Total Days", "Present", "Absent", "Attendance %"])
                writer.writerows(self.report_rows)
            messagebox.showinfo("Success", f"Report exported to:\n{file_path}")
        except OSError as exc:
            messagebox.showerror("File Error", str(exc))


def main() -> None:
    root = tk.Tk()
    AttendanceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
