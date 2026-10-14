"""
Unit and Integration Tests for Tkinter Desktop GUI Layer.
Validates window lifecycle, role-based tab access, dialog flows, and cart widgets.
Designed to run reliably both locally and in headless/CI test environments.
"""
import unittest
import os
import shutil
import tempfile
import tkinter as tk

from src.database.manager import DatabaseManager
from src.audit.logger import AuditLogger
from src.auth.service import AuthService
from src.menu.service import MenuService
from src.billing.service import BillingService
from src.billing.exporter import ExportService
from src.gui.main_window import MainWindow


class TestGUILayer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Verify Tkinter is supported in current environment
        try:
            root = tk.Tk()
            root.withdraw()
            root.destroy()
            cls.tk_available = True
        except Exception:
            cls.tk_available = False

    def setUp(self):
        if not self.tk_available:
            self.skipTest("Tkinter display not available in current headless environment.")

        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_gui.db")

        self.db = DatabaseManager(db_path=self.db_path)
        self.db.initialize_schema()
        self.audit = AuditLogger(db_manager=self.db)
        self.auth = AuthService(db_manager=self.db, audit_engine=self.audit)
        self.menu = MenuService(db_manager=self.db, audit_engine=self.audit)
        self.billing = BillingService(db_manager=self.db, audit_engine=self.audit)
        self.exporter = ExportService(db_manager=self.db, billing_engine=self.billing, menu_engine=self.menu)

        # Setup initial admin and cashier accounts
        self.auth.initial_setup_admin("admin", "AdminPass@2026", "MasterKey@Secret99")
        _, self.admin_session, _ = self.auth.login("admin", "AdminPass@2026")
        self.auth.create_staff_account(self.admin_session, "cashier1", "CashierPass@2026", "Cashier")
        self.auth.logout()

        _, self.cashier_session, _ = self.auth.login("cashier1", "CashierPass@2026")
        self.auth.logout()

    def tearDown(self):
        if hasattr(self, "app") and self.app:
            try:
                self.app.destroy()
            except Exception:
                pass
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_main_window_initialization(self):
        """Verifies MainWindow shell initializes with all status indicators."""
        self.app = MainWindow(
            self.db, self.auth, self.menu, self.billing, self.exporter, self.audit
        )
        self.app.withdraw()  # keep hidden during tests

        self.assertIsNotNone(self.app.notebook)
        self.assertIn("Gourmet Haven POS", self.app.title())
        self.assertEqual(self.app.user_lbl.cget("text"), "Not Logged In")

    def test_role_based_tabs_cashier(self):
        """Verifies cashier session only mounts POS Billing tab."""
        self.app = MainWindow(
            self.db, self.auth, self.menu, self.billing, self.exporter, self.audit
        )
        self.app.withdraw()

        self.app._on_login_success(self.cashier_session)
        tabs = self.app.notebook.tabs()
        # Cashier should only see POS Billing
        self.assertEqual(len(tabs), 1)
        tab_text = self.app.notebook.tab(tabs[0], "text")
        self.assertIn("POS Billing", tab_text)

    def test_role_based_tabs_admin(self):
        """Verifies admin session mounts all 4 tabs: Billing, Menu, Audit, Settings."""
        self.app = MainWindow(
            self.db, self.auth, self.menu, self.billing, self.exporter, self.audit
        )
        self.app.withdraw()

        self.app._on_login_success(self.admin_session)
        tabs = self.app.notebook.tabs()
        # Admin should see all 4 tabs
        self.assertEqual(len(tabs), 4)

    def test_billing_view_cart_calculation(self):
        """Verifies live cart calculation reflects in BillingView labels."""
        self.app = MainWindow(
            self.db, self.auth, self.menu, self.billing, self.exporter, self.audit
        )
        self.app.withdraw()
        self.app._on_login_success(self.cashier_session)

        bv = self.app.billing_view
        # Add item to cart
        bv.cart.add_item(item_id=1, item_name="Test Burger", unit_price=100.0, quantity=2)
        bv._update_cart_view()

        # Subtotal should be 200.00
        self.assertIn("200.00", bv.subtotal_lbl.cget("text"))
        self.assertIn("GST (5.0%)", bv.tax_lbl.cget("text"))

    def test_logout_workflow(self):
        """Verifies logout clears active session and resets tabs."""
        self.app = MainWindow(
            self.db, self.auth, self.menu, self.billing, self.exporter, self.audit
        )
        self.app.withdraw()
        self.app._on_login_success(self.admin_session)
        self.assertEqual(len(self.app.notebook.tabs()), 4)

        # Trigger logout
        self.app.logout()
        self.assertIsNone(self.app.session)
        self.assertEqual(len(self.app.notebook.tabs()), 0)


if __name__ == "__main__":
    unittest.main()
