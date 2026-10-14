"""
Central Main Window Application Shell for Restaurant Billing System.
Features role-based tab routing, live session tracking, and graceful shutdown.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from src.gui.login_dialog import LoginDialog
from src.gui.billing_view import BillingView
from src.gui.menu_view import MenuView
from src.gui.audit_view import AuditView
from src.gui.settings_view import SettingsView


class MainWindow(tk.Tk):
    """Primary application frame hosting role-aware navigation notebook."""
    def __init__(self, db_manager, auth_service, menu_service, billing_service, export_service, audit_logger):
        super().__init__()
        self.db = db_manager
        self.auth_service = auth_service
        self.menu_service = menu_service
        self.billing_service = billing_service
        self.export_service = export_service
        self.audit_logger = audit_logger

        self.session = None

        self.title("Gourmet Haven POS - Restaurant Billing System (BBAT104)")
        self.geometry("1100x720")
        self.minsize(960, 600)

        # Style configuration
        self._configure_styles()

        # Build UI layout
        self._build_header()
        self._build_notebook()
        self._build_statusbar()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Prompt login modal
        self.after(100, self.prompt_login)

    def _configure_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

    def _build_header(self):
        self.header_frame = ttk.Frame(self, padding="12 8 12 8")
        self.header_frame.pack(fill=tk.X)

        title_lbl = ttk.Label(
            self.header_frame,
            text="Gourmet Haven POS",
            font=("Segoe UI", 14, "bold"),
            foreground="#0f172a"
        )
        title_lbl.pack(side=tk.LEFT)

        subtitle_lbl = ttk.Label(
            self.header_frame,
            text=" | Quality Goal: Q04 Improve Security",
            font=("Segoe UI", 10),
            foreground="#64748b"
        )
        subtitle_lbl.pack(side=tk.LEFT)

        # Session user indicator
        self.user_lbl = ttk.Label(
            self.header_frame,
            text="Not Logged In",
            font=("Segoe UI", 10, "bold"),
            foreground="#dc2626"
        )
        self.user_lbl.pack(side=tk.RIGHT, padx=(10, 0))

        self.logout_btn = ttk.Button(
            self.header_frame,
            text="Switch User / Logout",
            command=self.logout
        )
        self.logout_btn.pack(side=tk.RIGHT)

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # Views
        self.billing_view = BillingView(
            self.notebook,
            self.menu_service,
            self.billing_service,
            self.export_service,
            get_session_callback=lambda: self.session
        )
        self.menu_view = MenuView(
            self.notebook,
            self.menu_service,
            get_session_callback=lambda: self.session,
            on_menu_changed_callback=self.billing_view.refresh_menu
        )
        self.audit_view = AuditView(
            self.notebook,
            self.audit_logger,
            get_session_callback=lambda: self.session
        )
        self.settings_view = SettingsView(
            self.notebook,
            self.billing_service,
            self.auth_service,
            self.export_service,
            get_session_callback=lambda: self.session
        )

        # Tabs are populated dynamically based on role in _update_role_tabs()

    def _build_statusbar(self):
        self.statusbar = ttk.Frame(self, padding="6 4 6 4")
        self.statusbar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_left = ttk.Label(
            self.statusbar,
            text="System Ready | Database: SQLite (WAL)",
            font=("Segoe UI", 8),
            foreground="#64748b"
        )
        self.status_left.pack(side=tk.LEFT)

        self.status_right = ttk.Label(
            self.statusbar,
            text="Student: Jatin Palariya (2410301034) | Fundamentals of TQM",
            font=("Segoe UI", 8),
            foreground="#64748b"
        )
        self.status_right.pack(side=tk.RIGHT)

    def prompt_login(self):
        """Displays modal login dialog."""
        LoginDialog(self, self.auth_service, on_success_callback=self._on_login_success)

    def _on_login_success(self, session):
        self.session = session
        role = session.role.upper()
        self.user_lbl.config(
            text=f"User: {session.username} ({role})",
            foreground="#166534"
        )
        self._update_role_tabs()

    def _update_role_tabs(self):
        """Mounts permitted tabs in the notebook according to session role."""
        # Clear existing tabs
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)

        if not self.session:
            return

        role = self.session.role.lower()

        # All roles get POS Billing
        self.notebook.add(self.billing_view, text="  POS Billing  ")
        self.billing_view.refresh_menu()

        # Manager and Admin get Menu Management
        if role in ("manager", "admin"):
            self.notebook.add(self.menu_view, text="  Menu Catalog  ")
            self.menu_view.refresh()

        # Admin gets Audit Logs & Settings
        if role == "admin":
            self.notebook.add(self.audit_view, text="  Audit Trail (SHA-256)  ")
            self.audit_view.refresh()

            self.notebook.add(self.settings_view, text="  Admin Settings & GST  ")
            self.settings_view.refresh()

        self.notebook.select(0)

    def logout(self):
        if self.session:
            try:
                self.auth_service.logout()
            except Exception:
                pass
            self.session = None

        self.user_lbl.config(text="Not Logged In", foreground="#dc2626")
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)
        self.prompt_login()

    def _on_close(self):
        if self.session:
            try:
                self.auth_service.logout()
            except Exception:
                pass
        self.destroy()
