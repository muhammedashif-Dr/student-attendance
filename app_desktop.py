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

    # Remaining methods identical to original app.py version (omitted here for brevity)


def main() -> None:
    root = tk.Tk()
    AttendanceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
