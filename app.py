"""
app.py
------
Frontend/controller layer: the Tk root window, ttk theming, and screen
navigation for the Job Portal Management System. Run this file to launch
the application.

    python app.py

Depends on:
    backend.py  -> database + business logic
    ui.py       -> individual screens (frames)
"""

import tkinter as tk
from tkinter import ttk

import backend
import ui


APP_TITLE = "Job Portal Management System"
WINDOW_SIZE = "1000x680"


def configure_style(root: tk.Tk):
    """Central place for the app's visual theme."""
    style = ttk.Style(root)
    # 'clam' themes best across platforms for custom colors.
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    bg = "#f4f6fb"
    accent = "#2f6fed"
    header_bg = "#1f2a44"
    card_bg = "#ffffff"

    root.configure(bg=bg)

    style.configure("TFrame", background=bg)
    style.configure("Card.TFrame", background=card_bg, relief="flat", borderwidth=1)
    style.configure("Header.TFrame", background=header_bg)

    style.configure("TLabel", background=bg, font=("Segoe UI", 10))
    style.configure("Title.TLabel", background=card_bg, font=("Segoe UI", 18, "bold"))
    style.configure("Hint.TLabel", background=bg, foreground="#7a7f8a", font=("Segoe UI", 8))
    style.configure(
        "HeaderTitle.TLabel", background=header_bg, foreground="white",
        font=("Segoe UI", 14, "bold")
    )
    style.configure(
        "HeaderSub.TLabel", background=header_bg, foreground="#c9d2e8",
        font=("Segoe UI", 9)
    )
    style.map("Card.TFrame", background=[("active", card_bg)])
    # Card.TFrame children labels should sit on card_bg too
    style.configure("TEntry", padding=4)
    style.configure("TButton", padding=6, font=("Segoe UI", 9))
    style.configure(
        "Accent.TButton", padding=6, font=("Segoe UI", 9, "bold"),
        background=accent, foreground="white"
    )
    style.map(
        "Accent.TButton",
        background=[("active", "#255bcc"), ("disabled", "#a9b8e0")],
    )
    style.configure("TNotebook", background=bg)
    style.configure("TNotebook.Tab", padding=(14, 8), font=("Segoe UI", 9))


class JobPortalApp(tk.Tk):
    """Root application window; owns navigation state and the logged-in user."""

    FRAME_CLASSES = {
        "LoginFrame": ui.LoginFrame,
        "RegisterFrame": ui.RegisterFrame,
        "SeekerDashboard": ui.SeekerDashboard,
        "EmployerDashboard": ui.EmployerDashboard,
        "AdminDashboard": ui.AdminDashboard,
    }

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self.minsize(860, 600)

        configure_style(self)

        self.current_user = None  # dict from backend.login_user

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        self.container = container

        self.frames = {}
        for name, cls in self.FRAME_CLASSES.items():
            frame = cls(container, self)
            self.frames[name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("LoginFrame")

    # ---------------- navigation ----------------
    def show_frame(self, name):
        frame = self.frames[name]
        frame.tkraise()
        if hasattr(frame, "refresh"):
            frame.refresh()

    def route_after_login(self):
        role = self.current_user["role"]
        target = {
            "seeker": "SeekerDashboard",
            "employer": "EmployerDashboard",
            "admin": "AdminDashboard",
        }[role]
        self.show_frame(target)

    def logout(self):
        self.current_user = None
        self.show_frame("LoginFrame")

    def open_notifications(self):
        if self.current_user:
            ui.NotificationsWindow(self, self)


def main():
    backend.init_db()
    app = JobPortalApp()
    app.mainloop()


if __name__ == "__main__":
    main()
