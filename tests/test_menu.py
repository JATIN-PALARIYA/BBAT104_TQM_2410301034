"""Unit and RBAC Tests for Menu Catalog CRUD Module
Restaurant Billing System [Q04: Improve Security] - BBAT104
Student: Jatin Palariya (Roll No: 2410301034)
"""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.audit import AuditLogger
from src.auth import UserSession
from src.database import DatabaseManager
from src.menu import MenuService


class TestMenuCatalog(unittest.TestCase):
    """Test suite covering menu catalog search, Admin CRUD, soft-deactivation, and Poka-Yoke guards."""

    def setUp(self):
        """Create an isolated temporary database with seed menu items."""
        self.test_db_path = BASE_DIR / "tests" / "test_menu_scratch.db"
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        self.db = DatabaseManager(self.test_db_path)
        self.db.initialize_schema()
        self.audit = AuditLogger(self.db)
        self.menu = MenuService(self.db, self.audit)

        # Mock sessions
        self.admin_session = UserSession(user_id=1, username="admin", role="Admin", must_change_password=False)
        self.cashier_session = UserSession(user_id=2, username="cashier1", role="Cashier", must_change_password=False)

    def tearDown(self):
        """Clean up test database files."""
        if self.test_db_path.exists():
            try:
                self.test_db_path.unlink()
            except PermissionError:
                pass

    def test_default_seeded_menu_retrieval(self):
        """Verify that all 10 baseline seeded menu items are retrieved."""
        items = self.menu.get_active_menu()
        self.assertEqual(len(items), 10)

    def test_category_filtering_and_search(self):
        """Verify category filtering and keyword search."""
        # Category filter
        beverages = self.menu.get_active_menu(category="Beverages")
        self.assertTrue(all(i["category"] == "Beverages" for i in beverages))
        self.assertEqual(len(beverages), 2)  # Masala Chai, Cold Coffee

        # Search filter
        search_results = self.menu.get_active_menu(search_query="Paneer")
        self.assertTrue(all("Paneer" in i["item_name"] for i in search_results))
        self.assertEqual(len(search_results), 2)  # Paneer Tikka, Butter Paneer Masala

    def test_admin_add_menu_item(self):
        """Verify Admin can add a new valid menu item."""
        success, item_id, msg = self.menu.add_menu_item(
            self.admin_session, "Veg Biryani", "Main Course", 220.00
        )
        self.assertTrue(success, msg)
        self.assertGreater(item_id, 10)

        item = self.menu.get_item_by_id(item_id)
        self.assertEqual(item["item_name"], "Veg Biryani")
        self.assertEqual(item["price"], 220.00)

    def test_poka_yoke_price_rejection_in_menu(self):
        """Verify that negative or zero prices are rejected when adding or updating items."""
        # Zero price rejected
        success, _, msg = self.menu.add_menu_item(
            self.admin_session, "Free Water", "Beverages", 0.00
        )
        self.assertFalse(success)
        self.assertIn("Poka-Yoke", msg)

        # Negative price rejected
        success, _, msg = self.menu.add_menu_item(
            self.admin_session, "Bad Item", "Starters", -50.00
        )
        self.assertFalse(success)
        self.assertIn("Poka-Yoke", msg)

    def test_poka_yoke_duplicate_name_rejection(self):
        """Verify duplicate item names are rejected."""
        success, _, msg = self.menu.add_menu_item(
            self.admin_session, "Masala Chai", "Beverages", 35.00
        )
        self.assertFalse(success)
        self.assertIn("already exists", msg)

    def test_rbac_cashier_cannot_modify_menu(self):
        """Verify that cashiers are blocked from adding, editing, or deactivating items."""
        # Cashier tries to add
        success, _, msg = self.menu.add_menu_item(
            self.cashier_session, "Unauthorized Item", "Beverages", 40.00
        )
        self.assertFalse(success)
        self.assertIn("Access Denied", msg)

        # Cashier tries to update
        success, msg = self.menu.update_menu_item(
            self.cashier_session, 1, "Discounted Chai", "Beverages", 10.00
        )
        self.assertFalse(success)
        self.assertIn("Access Denied", msg)

        # Cashier tries to deactivate
        success, msg = self.menu.toggle_item_status(self.cashier_session, 1, False)
        self.assertFalse(success)
        self.assertIn("Access Denied", msg)

    def test_soft_deactivation_preserves_historical_records(self):
        """Verify that soft-deactivating an item hides it from active menu but preserves it in admin view."""
        # Deactivate item #1 (Masala Chai)
        success, msg = self.menu.toggle_item_status(self.admin_session, 1, False)
        self.assertTrue(success, msg)

        # Masala Chai no longer appears in cashier active menu
        active_items = self.menu.get_active_menu()
        self.assertEqual(len(active_items), 9)
        self.assertFalse(any(i["item_id"] == 1 for i in active_items))

        # Masala Chai still exists in database for past invoices and admin list
        all_items = self.menu.get_all_items_admin()
        self.assertEqual(len(all_items), 10)
        item1 = next(i for i in all_items if i["item_id"] == 1)
        self.assertEqual(item1["is_active"], 0)

        # Reactivate item
        success, msg = self.menu.toggle_item_status(self.admin_session, 1, True)
        self.assertTrue(success)
        self.assertEqual(len(self.menu.get_active_menu()), 10)


if __name__ == "__main__":
    unittest.main()
