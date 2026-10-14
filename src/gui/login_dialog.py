"""
Login Dialog Modal for Authentication and Session Establishment.
Implements Poka-Yoke input guards, password masking, and lockout feedback.
"""
import tkinter as tk
from tkinter import ttk, messagebox


class LoginDialog(tk.Toplevel):
    """
    Modal authentication window shown on application launch or session switch.
    """
    def __init__(self, parent, auth_service, on_success_callback):
        super().__init__(parent)
        self.auth_service = auth_service
        self.on_success = on_success_callback
        self.session = None

        self.title("Authentication - Restaurant Billing System")
        self.geometry("420x460")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Center on parent or screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 420) // 2
        y = (self.winfo_screenheight() - 460) // 2
        self.geometry(f"+{x}+{y}")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding="24 20 24 20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title & Branding
        brand_lbl = ttk.Label(
            main_frame,
            text="Gourmet Haven POS",
            font=("Segoe UI", 16, "bold"),
            foreground="#1e293b"
        )
        brand_lbl.pack(pady=(0, 4))

        sub_lbl = ttk.Label(
            main_frame,
            text="Secure Role-Based Staff Sign-In",
            font=("Segoe UI", 10),
            foreground="#64748b"
        )
        sub_lbl.pack(pady=(0, 20))

        # Username
        ttk.Label(main_frame, text="Username:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(main_frame, textvariable=self.username_var, font=("Segoe UI", 11))
        self.username_entry.pack(fill=tk.X, pady=(0, 14), ipady=3)
        self.username_entry.focus_set()

        # Password
        ttk.Label(main_frame, text="Password:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(
            main_frame,
            textvariable=self.password_var,
            show="*",
            font=("Segoe UI", 11)
        )
        self.password_entry.pack(fill=tk.X, pady=(0, 8), ipady=3)

        # Show password toggle
        self.show_pwd_var = tk.BooleanVar(value=False)
        self.show_pwd_cb = ttk.Checkbutton(
            main_frame,
            text="Show Password",
            variable=self.show_pwd_var,
            command=self._toggle_password_visibility
        )
        self.show_pwd_cb.pack(anchor=tk.W, pady=(0, 16))

        # Error / Status label
        self.status_var = tk.StringVar(value="")
        self.status_lbl = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 9),
            foreground="#dc2626",
            wraplength=360
        )
        self.status_lbl.pack(fill=tk.X, pady=(0, 12))

        # Login Button
        self.login_btn = ttk.Button(
            main_frame,
            text="Sign In",
            command=self._handle_login
        )
        self.login_btn.pack(fill=tk.X, ipady=6, pady=(0, 10))

        # Key Bindings
        self.bind("<Return>", lambda event: self._handle_login())
        self.bind("<Escape>", lambda event: self._on_close())

        # Footer Hint
        hint_lbl = ttk.Label(
            main_frame,
            text="Default Admin: admin / AdminPass@2026\nDefault Cashier: cashier1 / CashierPass@2026",
            font=("Segoe UI", 8),
            foreground="#94a3b8",
            justify=tk.CENTER
        )
        hint_lbl.pack(side=tk.BOTTOM, pady=(10, 0))

    def _toggle_password_visibility(self):
        if self.show_pwd_var.get():
            self.password_entry.config(show="")
        else:
            self.password_entry.config(show="*")

    def _handle_login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()

        if not username or not password:
            self.status_var.set("Please enter both username and password.")
            return

        self.login_btn.config(state=tk.DISABLED)
        self.status_var.set("Authenticating credentials...")
        self.update_idletasks()

        try:
            success, session, message = self.auth_service.login(username=username, password=password)
            if success and session:
                self.session = session
                self.status_var.set("")
                self.destroy()
                if self.on_success:
                    self.on_success(session)
            else:
                self.status_var.set(message or "Invalid credentials or account locked.")
                self.login_btn.config(state=tk.NORMAL)
                self.password_entry.focus_set()
                self.password_entry.selection_range(0, tk.END)
        except Exception as ex:
            self.status_var.set(str(ex))
            self.login_btn.config(state=tk.NORMAL)
            self.password_entry.focus_set()
            self.password_entry.selection_range(0, tk.END)

    def _on_close(self):
        if self.session is None:
            # If closed without logging in, ask to exit application
            if messagebox.askyesno("Exit Application", "Quit Restaurant Billing System?", parent=self):
                self.master.destroy()
        else:
            self.destroy()
