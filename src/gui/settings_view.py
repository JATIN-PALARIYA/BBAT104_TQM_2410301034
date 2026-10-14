"""
System Configuration & Tax Settings Viewport for Administrators.
Provides customizable GST rate updates, staff account maintenance, and data export.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog


class SettingsView(ttk.Frame):
    """Admin configuration control panel."""
    def __init__(self, parent, billing_service, auth_service, export_service, get_session_callback):
        super().__init__(parent)
        self.billing_service = billing_service
        self.auth_service = auth_service
        self.export_service = export_service
        self.get_session = get_session_callback

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        container = ttk.Frame(self, padding="16")
        container.pack(fill=tk.BOTH, expand=True)

        # 1. Tax Rate Configuration (Requested: Custom GST changed by Admin)
        tax_frame = ttk.LabelFrame(container, text="GST & Tax Rate Configuration", padding="12")
        tax_frame.pack(fill=tk.X, pady=(0, 14))

        tax_grid = ttk.Frame(tax_frame)
        tax_grid.pack(fill=tk.X)

        ttk.Label(tax_grid, text="Active GST Rate (%):").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.tax_pct_var = tk.StringVar()
        tax_entry = ttk.Entry(tax_grid, textvariable=self.tax_pct_var, width=10)
        tax_entry.grid(row=0, column=1, sticky=tk.W, padx=(8, 12), pady=4)

        ttk.Button(tax_grid, text="Update GST Rate", command=self._update_tax).grid(row=0, column=2, sticky=tk.W, pady=4)

        tax_hint = ttk.Label(
            tax_frame,
            text="* Poka-Yoke Bounds: Allowed tax rates range between 0.0% and 50.0%.\n"
                 "Changes are dynamically applied to all new orders and audit-logged.",
            font=("Segoe UI", 8),
            foreground="#64748b"
        )
        tax_hint.pack(anchor=tk.W, pady=(6, 0))

        # 2. Staff Account Management
        staff_frame = ttk.LabelFrame(container, text="Staff Account Management", padding="12")
        staff_frame.pack(fill=tk.X, pady=(0, 14))

        staff_btns = ttk.Frame(staff_frame)
        staff_btns.pack(fill=tk.X)

        ttk.Button(staff_btns, text="Create Staff Account", command=self._open_create_staff).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(staff_btns, text="Reset Staff Password", command=self._open_reset_password).pack(side=tk.LEFT, padx=(0, 8))

        # 3. Data Export Center
        export_frame = ttk.LabelFrame(container, text="Repository Data Export Center", padding="12")
        export_frame.pack(fill=tk.X)

        export_btns = ttk.Frame(export_frame)
        export_btns.pack(fill=tk.X)

        ttk.Button(export_btns, text="Export Invoices (CSV)", command=self._export_invoices_csv).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(export_btns, text="Export Invoices (JSON)", command=self._export_invoices_json).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(export_btns, text="Export Menu Catalog (CSV)", command=self._export_menu_csv).pack(side=tk.LEFT, padx=(0, 8))

    def refresh(self):
        """Loads active GST percentage."""
        try:
            rate = self.billing_service.get_tax_rate()
            self.tax_pct_var.set(f"{rate * 100.0:.1f}")
        except Exception as ex:
            messagebox.showerror("Error", str(ex), parent=self)

    def _update_tax(self):
        try:
            pct = float(self.tax_pct_var.get().strip())
            rate = pct / 100.0
            session = self.get_session()
            ok, msg = self.billing_service.update_tax_rate(admin_session=session, new_rate=rate)
            if ok:
                messagebox.showinfo(
                    "Tax Rate Updated",
                    f"GST rate successfully updated to {pct:.1f}%.\nAll subsequent orders will apply this rate.",
                    parent=self
                )
                self.refresh()
            else:
                messagebox.showerror("Update Failed", msg, parent=self)
        except Exception as ex:
            messagebox.showerror("Update Error", str(ex), parent=self)

    def _open_create_staff(self):
        CreateStaffDialog(self, self.auth_service, self.get_session())

    def _open_reset_password(self):
        ResetStaffDialog(self, self.auth_service, self.get_session())

    def _export_invoices_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Documents", "*.csv")],
            initialfile="all_invoices_export.csv",
            title="Export Invoices to CSV"
        )
        if path:
            try:
                ok, msg = self.export_service.export_invoices_to_csv(path, session=self.get_session())
                if ok:
                    messagebox.showinfo("Export Complete", f"Invoices exported to:\n{path}", parent=self)
                else:
                    messagebox.showerror("Export Failed", msg, parent=self)
            except Exception as ex:
                messagebox.showerror("Export Error", str(ex), parent=self)

    def _export_invoices_json(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Documents", "*.json")],
            initialfile="all_invoices_export.json",
            title="Export Invoices to JSON"
        )
        if path:
            try:
                ok, msg = self.export_service.export_invoices_to_json(path, session=self.get_session())
                if ok:
                    messagebox.showinfo("Export Complete", f"Invoices exported to:\n{path}", parent=self)
                else:
                    messagebox.showerror("Export Failed", msg, parent=self)
            except Exception as ex:
                messagebox.showerror("Export Error", str(ex), parent=self)

    def _export_menu_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Documents", "*.csv")],
            initialfile="menu_catalog_export.csv",
            title="Export Menu to CSV"
        )
        if path:
            try:
                ok, msg = self.export_service.export_menu_to_csv(path)
                if ok:
                    messagebox.showinfo("Export Complete", f"Menu exported to:\n{path}", parent=self)
                else:
                    messagebox.showerror("Export Failed", msg, parent=self)
            except Exception as ex:
                messagebox.showerror("Export Error", str(ex), parent=self)


class CreateStaffDialog(tk.Toplevel):
    """Modal for creating new staff account."""
    def __init__(self, parent, auth_service, session):
        super().__init__(parent)
        self.auth_service = auth_service
        self.session = session

        self.title("Create Staff Account")
        self.geometry("360x320")
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding="16")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Username:").pack(anchor=tk.W, pady=(0, 2))
        self.user_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.user_var).pack(fill=tk.X, pady=(0, 8))

        ttk.Label(frame, text="Temporary Password:").pack(anchor=tk.W, pady=(0, 2))
        self.pwd_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.pwd_var, show="*").pack(fill=tk.X, pady=(0, 8))

        ttk.Label(frame, text="Role:").pack(anchor=tk.W, pady=(0, 2))
        self.role_var = tk.StringVar(value="Cashier")
        ttk.Combobox(frame, textvariable=self.role_var, values=["Cashier", "Manager"], state="readonly").pack(fill=tk.X, pady=(0, 16))

        ttk.Button(frame, text="Create Account", command=self._create).pack(fill=tk.X, ipady=4)

    def _create(self):
        u = self.user_var.get().strip()
        p = self.pwd_var.get()
        r = self.role_var.get()
        try:
            ok, msg = self.auth_service.create_staff_account(admin_session=self.session, username=u, temp_password=p, role=r)
            if ok:
                messagebox.showinfo("Success", f"Account '{u}' created successfully.", parent=self)
                self.destroy()
            else:
                messagebox.showerror("Creation Failed", msg, parent=self)
        except Exception as ex:
            messagebox.showerror("Error", str(ex), parent=self)


class ResetStaffDialog(tk.Toplevel):
    """Modal for administrative password reset."""
    def __init__(self, parent, auth_service, session):
        super().__init__(parent)
        self.auth_service = auth_service
        self.session = session

        self.title("Reset Staff Password")
        self.geometry("360x280")
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding="16")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Username:").pack(anchor=tk.W, pady=(0, 2))
        self.user_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.user_var).pack(fill=tk.X, pady=(0, 8))

        ttk.Label(frame, text="New Password:").pack(anchor=tk.W, pady=(0, 2))
        self.pwd_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.pwd_var, show="*").pack(fill=tk.X, pady=(0, 16))

        ttk.Button(frame, text="Reset Password", command=self._reset).pack(fill=tk.X, ipady=4)

    def _reset(self):
        u = self.user_var.get().strip()
        p = self.pwd_var.get()
        try:
            ok, msg = self.auth_service.admin_reset_staff_password(admin_session=self.session, target_username=u, new_temp_password=p)
            if ok:
                messagebox.showinfo("Success", f"Password for '{u}' has been reset.", parent=self)
                self.destroy()
            else:
                messagebox.showerror("Reset Failed", msg, parent=self)
        except Exception as ex:
            messagebox.showerror("Error", str(ex), parent=self)
