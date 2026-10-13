"""Unit, Integration, and RBAC Security Tests for Menu Categories Management.
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)

Verifies:
1. Category creation, duplication prevention, and empty name guards.
2. Case-insensitive uniqueness enforcement and reserved keyword protection.
3. Safe category renaming with automatic menu item cascade updates.
4. Safe category deletion requiring item reassignment to eliminate orphaned items.
5. Role-based access control blocking Cashiers from mutating categories.
6. Cryptographic audit trail logging for all category mutations.
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


class TestMenuCategories(unittest.TestCase):
    """Test suite covering category lifecycle, validations, and orphaned item protection."""

    def setUp(self):
        self.test_db_path = BASE_DIR / "tests" / "test_categories_scratch.db"
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        self.db = DatabaseManager(self.test_db_path)
        self.db.initialize_schema()
        self.audit = AuditLogger(self.db)
        self.menu = MenuService(self.db, self.audit)

        self.admin = UserSession(user_id=1, username="admin", role="Admin", must_change_password=False)
        self.cashier = UserSession(user_id=2, username="cashier1", role="Cashier", must_change_password=False)

    def tearDown(self):
        if self.test_db_path.exists():
            try:
                self.test_db_path.unlink()
            except PermissionError:
                pass

    def test_default_categories_seeded(self):
        """Verify baseline 5 categories are pre-populated in database."""
        cats = self.menu.get_categories()
        expected = ["Beverages", "Starters", "Main Course", "Desserts", "Breads & Rice"]
        for exp in expected:
            self.assertIn(exp, cats)

        counts = self.menu.get_categories_with_counts()
        self.assertEqual(len(counts), 5)
        # Check that items in seed match counts
        bev = next(c for c in counts if c["category_name"] == "Beverages")
        self.assertEqual(bev["total_items"], 2)

    def test_admin_add_category_success(self):
        """Verify Admin can create a custom category and add items to it."""
        success, msg = self.menu.add_category(self.admin, "Soups & Salads")
        self.assertTrue(success, msg)
        self.assertIn("Soups & Salads", self.menu.get_categories())

        # Admin can now add items to this new custom category
        ok, item_id, imsg = self.menu.add_menu_item(
            self.admin, "Tomato Basil Soup", "Soups & Salads", 120.00
        )
        self.assertTrue(ok, imsg)
        item = self.menu.get_item_by_id(item_id)
        self.assertEqual(item["category"], "Soups & Salads")

        # Verify audit log recorded
        logs = self.audit.get_logs(limit=5)
        cat_log = next((l for l in logs if l["action_type"] == "CATEGORY_ADDED"), None)
        self.assertIsNotNone(cat_log)
        self.assertIn("Soups & Salads", cat_log["details"])

    def test_add_category_empty_or_short_name_rejected(self):
        """Verify empty, whitespace, or single-character names are rejected."""
        # Empty string
        ok1, msg1 = self.menu.add_category(self.admin, "")
        self.assertFalse(ok1)
        self.assertIn("at least 2 characters", msg1)

        # Whitespace only
        ok2, msg2 = self.menu.add_category(self.admin, "   ")
        self.assertFalse(ok2)
        self.assertIn("at least 2 characters", msg2)

        # Single character
        ok3, msg3 = self.menu.add_category(self.admin, "X")
        self.assertFalse(ok3)
        self.assertIn("at least 2 characters", msg3)

    def test_add_category_duplicate_rejection(self):
        """Verify duplicate category names are rejected case-insensitively."""
        # Existing category
        ok1, msg1 = self.menu.add_category(self.admin, "Beverages")
        self.assertFalse(ok1)
        self.assertIn("already exists", msg1)

        # Case-insensitive duplicate (e.g. 'beverages')
        ok2, msg2 = self.menu.add_category(self.admin, "beverages")
        self.assertFalse(ok2)
        self.assertIn("already exists", msg2)

    def test_add_category_reserved_name_rejected(self):
        """Verify reserved filter keyword 'All' cannot be created as a category."""
        ok1, msg1 = self.menu.add_category(self.admin, "All")
        self.assertFalse(ok1)
        self.assertIn("reserved", msg1)

        ok2, msg2 = self.menu.add_category(self.admin, "all")
        self.assertFalse(ok2)
        self.assertIn("reserved", msg2)

    def test_rename_category_safely_updates_menu_items(self):
        """Verify category rename updates menu_categories and all existing menu items."""
        # Baseline 'Beverages' has 2 items: Masala Chai (id 1) and Cold Coffee (id 2)
        ok, msg = self.menu.rename_category(self.admin, "Beverages", "Drinks & Shakes")
        self.assertTrue(ok, msg)
        self.assertIn("2 items updated", msg)

        # Check category list
        cats = self.menu.get_categories()
        self.assertNotIn("Beverages", cats)
        self.assertIn("Drinks & Shakes", cats)

        # Check existing menu items: zero orphaned records
        chai = self.menu.get_item_by_id(1)
        coffee = self.menu.get_item_by_id(2)
        self.assertEqual(chai["category"], "Drinks & Shakes")
        self.assertEqual(coffee["category"], "Drinks & Shakes")

        # Verify audit log
        logs = self.audit.get_logs(limit=5)
        log = next((l for l in logs if l["action_type"] == "CATEGORY_RENAMED"), None)
        self.assertIsNotNone(log)
        self.assertIn("Beverages", log["details"])
        self.assertIn("Drinks & Shakes", log["details"])

    def test_rename_category_duplicate_or_invalid_rejected(self):
        """Verify renaming to an existing category name or empty name is rejected."""
        # Non-existent source
        ok1, msg1 = self.menu.rename_category(self.admin, "NonExistentCat", "NewCat")
        self.assertFalse(ok1)
        self.assertIn("not found", msg1)

        # Target already exists
        ok2, msg2 = self.menu.rename_category(self.admin, "Beverages", "Starters")
        self.assertFalse(ok2)
        self.assertIn("already exists", msg2)

        # Target identical
        ok3, msg3 = self.menu.rename_category(self.admin, "Beverages", "Beverages")
        self.assertFalse(ok3)
        self.assertIn("identical", msg3)

        # Target empty
        ok4, msg4 = self.menu.rename_category(self.admin, "Beverages", " ")
        self.assertFalse(ok4)
        self.assertIn("at least 2 characters", msg4)

    def test_delete_empty_category(self):
        """Verify a category with zero items can be deleted cleanly."""
        self.menu.add_category(self.admin, "Special Combos")
        self.assertIn("Special Combos", self.menu.get_categories())

        ok, msg = self.menu.delete_category(self.admin, "Special Combos")
        self.assertTrue(ok, msg)
        self.assertNotIn("Special Combos", self.menu.get_categories())

        # Verify audit log
        logs = self.audit.get_logs(limit=5)
        log = next((l for l in logs if l["action_type"] == "CATEGORY_DELETED"), None)
        self.assertIsNotNone(log)
        self.assertIn("Special Combos", log["details"])

    def test_delete_category_with_items_requires_reassignment(self):
        """Verify deleting a populated category requires reassignment and leaves no orphans."""
        # 'Starters' has 2 items: Paneer Tikka (id 3) and Veg Spring Rolls (id 4)
        # Attempting deletion without reassign_to must fail
        ok1, msg1 = self.menu.delete_category(self.admin, "Starters")
        self.assertFalse(ok1)
        self.assertIn("Please select a destination category", msg1)

        # Now delete with reassign_to='Main Course'
        ok2, msg2 = self.menu.delete_category(self.admin, "Starters", reassign_to="Main Course")
        self.assertTrue(ok2, msg2)
        self.assertIn("2 items reassigned to 'Main Course'", msg2)
        self.assertNotIn("Starters", self.menu.get_categories())

        # Check previously 'Starters' items are now in 'Main Course'
        item3 = self.menu.get_item_by_id(3)
        item4 = self.menu.get_item_by_id(4)
        self.assertEqual(item3["category"], "Main Course")
        self.assertEqual(item4["category"], "Main Course")

        # Zero orphaned items
        all_items = self.menu.get_all_items_admin()
        valid_cats = self.menu.get_categories()
        for itm in all_items:
            self.assertIn(itm["category"], valid_cats)

    def test_delete_last_remaining_category_prevented(self):
        """Verify system prevents deleting the last remaining category."""
        # Delete down until 1 category remains
        cats = self.menu.get_categories()
        for c in cats[1:]:
            self.menu.delete_category(self.admin, c, reassign_to=cats[0])

        remaining = self.menu.get_categories()
        self.assertEqual(len(remaining), 1)

        # Attempting to delete the last category must be rejected
        ok, msg = self.menu.delete_category(self.admin, remaining[0])
        self.assertFalse(ok)
        self.assertIn("only remaining category", msg)

    def test_rbac_cashier_cannot_mutate_categories(self):
        """Verify Cashier role is blocked from adding, renaming, or deleting categories."""
        # Cashier tries to add
        ok1, msg1 = self.menu.add_category(self.cashier, "Unauthorized Category")
        self.assertFalse(ok1)
        self.assertIn("Access Denied", msg1)

        # Cashier tries to rename
        ok2, msg2 = self.menu.rename_category(self.cashier, "Beverages", "Cashier Drinks")
        self.assertFalse(ok2)
        self.assertIn("Access Denied", msg2)

        # Cashier tries to delete
        ok3, msg3 = self.menu.delete_category(self.cashier, "Beverages")
        self.assertFalse(ok3)
        self.assertIn("Access Denied", msg3)


if __name__ == "__main__":
    unittest.main()
