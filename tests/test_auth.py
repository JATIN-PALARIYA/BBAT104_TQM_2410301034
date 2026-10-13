"""Unit and Security Tests for Authentication, RBAC, and Password Reset
Restaurant Billing System [Q04: Improve Security] - BBAT104
Student: Jatin Palariya (Roll No: 2410301034)
"""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.audit import AuditLogger
from src.auth import AuthService
from src.database import DatabaseManager


class TestAuthenticationAndRBAC(unittest.TestCase):
    """Test suite covering Setup Wizard, Role-Based Login, Brute-Force Lockout, and Password Resets."""

    def setUp(self):
        """Create an isolated temporary database for auth tests."""
        self.test_db_path = BASE_DIR / "tests" / "test_auth_scratch.db"
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        self.db = DatabaseManager(self.test_db_path)
        self.db.initialize_schema()
        self.audit = AuditLogger(self.db)
        self.auth = AuthService(self.db, self.audit)

    def tearDown(self):
        """Clean up test database files."""
        if self.test_db_path.exists():
            try:
                self.test_db_path.unlink()
            except PermissionError:
                pass

    def test_setup_wizard_initial_admin(self):
        """Verify initial setup wizard creates Admin account and Master Recovery Key."""
        self.assertTrue(self.auth.is_setup_needed())

        success, msg = self.auth.initial_setup_admin("admin", "AdminPass@2026", "MasterKey@Secret99")
        self.assertTrue(success, msg)
        self.assertFalse(self.auth.is_setup_needed())

        # Second setup attempt must be rejected
        success, _ = self.auth.initial_setup_admin("admin2", "AdminPass@2026", "MasterKey@Secret99")
        self.assertFalse(success)

    def test_successful_login_and_session(self):
        """Verify valid credentials return active UserSession and clear session on logout."""
        self.auth.initial_setup_admin("admin", "AdminPass@2026", "MasterKey@Secret99")

        success, session, msg = self.auth.login("admin", "AdminPass@2026")
        self.assertTrue(success)
        self.assertIsNotNone(session)
        self.assertEqual(session.username, "admin")
        self.assertEqual(session.role, "Admin")
        self.assertTrue(session.is_admin())
        self.assertFalse(session.is_cashier())

        # Logout clears active session
        self.auth.logout()
        self.assertIsNone(self.auth.active_session)

    def test_brute_force_lockout_after_5_failed_attempts(self):
        """Verify account lockout is enforced after exactly 5 consecutive failed login attempts."""
        self.auth.initial_setup_admin("admin", "AdminPass@2026", "MasterKey@Secret99")

        # 4 consecutive invalid attempts should fail but not lock
        for i in range(1, 5):
            success, session, msg = self.auth.login("admin", f"WrongPass@{i}")
            self.assertFalse(success)
            self.assertIn("remaining", msg)

        # 5th failed attempt triggers lockout
        success, session, msg = self.auth.login("admin", "WrongPass@5")
        self.assertFalse(success)
        self.assertIn("Account locked", msg)

        # Subsequent attempt is blocked by lockout
        success, session, msg = self.auth.login("admin", "AdminPass@2026")
        self.assertFalse(success)
        self.assertIn("temporarily locked", msg)

    def test_admin_master_recovery_key_reset(self):
        """Verify Admin can reset forgotten password using the Master Recovery Key."""
        self.auth.initial_setup_admin("admin", "AdminPass@2026", "MasterKey@Secret99")

        # Admin forgets password and initiates recovery
        success, msg = self.auth.reset_admin_with_master_key("MasterKey@Secret99", "NewAdminPass@2027")
        self.assertTrue(success, msg)

        # Login with old password fails
        success, _, _ = self.auth.login("admin", "AdminPass@2026")
        self.assertFalse(success)

        # Login with new password succeeds
        success, session, _ = self.auth.login("admin", "NewAdminPass@2027")
        self.assertTrue(success)
        self.assertEqual(session.username, "admin")

    def test_admin_staff_account_creation_and_forced_password_change(self):
        """Verify Admin can create Cashier accounts with must_change_password=1 and cashier can change it."""
        self.auth.initial_setup_admin("admin", "AdminPass@2026", "MasterKey@Secret99")
        _, admin_session, _ = self.auth.login("admin", "AdminPass@2026")

        # Admin creates Cashier account
        success, msg = self.auth.create_staff_account(admin_session, "cashier1", "TempPass@1234")
        self.assertTrue(success, msg)

        # Cashier logs in with temporary password
        success, cashier_session, _ = self.auth.login("cashier1", "TempPass@1234")
        self.assertTrue(success)
        self.assertTrue(cashier_session.must_change_password)
        self.assertTrue(cashier_session.is_cashier())
        self.assertFalse(cashier_session.is_admin())

        # Cashier changes their password
        success, msg = self.auth.change_user_password("cashier1", "TempPass@1234", "MyNewCashier@5678")
        self.assertTrue(success, msg)

        # Cashier logs in with new password; must_change_password is now False
        success, cashier_session2, _ = self.auth.login("cashier1", "MyNewCashier@5678")
        self.assertTrue(success)
        self.assertFalse(cashier_session2.must_change_password)

    def test_rbac_cashier_cannot_create_staff_or_reset(self):
        """Verify RBAC: Cashiers cannot create users or reset staff passwords."""
        self.auth.initial_setup_admin("admin", "AdminPass@2026", "MasterKey@Secret99")
        _, admin_session, _ = self.auth.login("admin", "AdminPass@2026")
        self.auth.create_staff_account(admin_session, "cashier1", "TempPass@1234")

        # Login as Cashier
        _, cashier_session, _ = self.auth.login("cashier1", "TempPass@1234")

        # Cashier attempts administrative actions
        success, msg = self.auth.create_staff_account(cashier_session, "cashier2", "TempPass@1234")
        self.assertFalse(success)
        self.assertIn("Access Denied", msg)

        success, msg = self.auth.admin_reset_staff_password(cashier_session, "admin", "HackedPass@123")
        self.assertFalse(success)
        self.assertIn("Access Denied", msg)

    def test_staff_deactivation_and_reactivation(self):
        """Verify Admin can deactivate staff, deactivated staff cannot log in, and reactivation restores access."""
        self.auth.initial_setup_admin("admin", "AdminPass@2026", "MasterKey@Secret99")
        _, admin_session, _ = self.auth.login("admin", "AdminPass@2026")
        self.auth.create_staff_account(admin_session, "cashier1", "TempPass@1234")

        # Deactivate cashier
        success, msg = self.auth.set_staff_status(admin_session, "cashier1", "Inactive")
        self.assertTrue(success, msg)

        # Deactivated cashier cannot log in
        login_ok, _, login_msg = self.auth.login("cashier1", "TempPass@1234")
        self.assertFalse(login_ok)
        self.assertIn("deactivated", login_msg.lower())

        # Admin reactivates cashier
        success, msg = self.auth.set_staff_status(admin_session, "cashier1", "Active")
        self.assertTrue(success, msg)

        # Reactivated cashier logs in successfully
        login_ok, cashier_session, _ = self.auth.login("cashier1", "TempPass@1234")
        self.assertTrue(login_ok)
        self.assertIsNotNone(cashier_session)

        # Cashier cannot deactivate admin
        success, msg = self.auth.set_staff_status(cashier_session, "admin", "Inactive")
        self.assertFalse(success)
        self.assertIn("Access Denied", msg)

        # Admin cannot deactivate self
        success, msg = self.auth.set_staff_status(admin_session, "admin", "Inactive")
        self.assertFalse(success)
        self.assertIn("cannot change the status of your own account", msg)

    def test_staff_deletion(self):
        """Verify Admin can delete staff without invoices, but cannot delete accounts with invoices."""
        self.auth.initial_setup_admin("admin", "AdminPass@2026", "MasterKey@Secret99")
        _, admin_session, _ = self.auth.login("admin", "AdminPass@2026")
        self.auth.create_staff_account(admin_session, "cashier_temp", "TempPass@1234")

        # Admin deletes cashier_temp
        success, msg = self.auth.delete_staff_account(admin_session, "cashier_temp")
        self.assertTrue(success, msg)

        # Confirm user is removed from database
        user = self.db.fetch_one("SELECT * FROM users WHERE username = 'cashier_temp';")
        self.assertIsNone(user)

        # Cashier cannot delete accounts
        self.auth.create_staff_account(admin_session, "cashier_a", "TempPass@1234")
        _, cashier_session, _ = self.auth.login("cashier_a", "TempPass@1234")
        success, msg = self.auth.delete_staff_account(cashier_session, "cashier_a")
        self.assertFalse(success)
        self.assertIn("Access Denied", msg)

        # Admin cannot delete admin account
        success, msg = self.auth.delete_staff_account(admin_session, "admin")
        self.assertFalse(success)
        self.assertIn("cannot delete your own account", msg)


if __name__ == "__main__":
    unittest.main()
