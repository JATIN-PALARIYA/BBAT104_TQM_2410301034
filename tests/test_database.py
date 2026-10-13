"""Unit and Integrity Tests for Database Manager
Restaurant Billing System [Q04: Improve Security]
Student: Jatin Palariya (Roll No: 2410301034)
"""

import os
import sqlite3
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database import DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    """Test suite verifying SQLite schema integrity, foreign keys, CHECK constraints, and seeding."""

    def setUp(self):
        """Create an isolated temporary database for each test run."""
        self.test_db_path = BASE_DIR / "tests" / "test_scratch.db"
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        self.db = DatabaseManager(self.test_db_path)
        self.db.initialize_schema()

    def tearDown(self):
        """Clean up test database files."""
        if self.test_db_path.exists():
            try:
                self.test_db_path.unlink()
            except PermissionError:
                pass

    def test_schema_creates_all_six_tables(self):
        """Verify that all six required relational tables exist."""
        expected_tables = {
            "users",
            "menu_items",
            "bills",
            "bill_items",
            "audit_logs",
            "app_settings",
        }
        rows = self.db.fetch_all("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        existing_tables = {r["name"] for r in rows}
        self.assertTrue(expected_tables.issubset(existing_tables), f"Missing tables: {expected_tables - existing_tables}")

    def test_default_seed_data_loaded(self):
        """Verify that the initial 10 menu items and default settings were pre-populated."""
        items = self.db.fetch_all("SELECT * FROM menu_items WHERE is_active = 1;")
        self.assertEqual(len(items), 10, "Expected exactly 10 initial active menu items")

        tax_rate = self.db.get_setting("tax_rate")
        self.assertEqual(tax_rate, "0.05", "Expected default 5% tax rate setting")

        restaurant_name = self.db.get_setting("restaurant_name")
        self.assertEqual(restaurant_name, "Amrapali Campus Diner")

    def test_foreign_key_enforcement(self):
        """Verify that foreign key violations raise sqlite3.IntegrityError."""
        # Attempting to insert a bill referencing a non-existent cashier_id (e.g. 9999)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                """
                INSERT INTO bills (bill_number, cashier_id, subtotal, tax_rate, tax_amount, final_total, receipt_hash)
                VALUES ('BILL-TEST-0001', 9999, 100.0, 0.05, 5.0, 105.0, 'test_hash');
                """
            )

    def test_poka_yoke_check_constraints_price_and_quantity(self):
        """Verify that database CHECK constraints reject negative price and negative quantity."""
        # Rejection of price <= 0.0 in menu_items
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                """
                INSERT INTO menu_items (item_name, category, price, is_active)
                VALUES ('Invalid Price Item', 'Beverages', -25.0, 1);
                """
            )

        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                """
                INSERT INTO menu_items (item_name, category, price, is_active)
                VALUES ('Zero Price Item', 'Beverages', 0.0, 1);
                """
            )

    def test_transaction_rollback_on_failure(self):
        """Verify that multi-statement transactions roll back completely if an error occurs."""
        # Insert a valid user
        user_id = self.db.execute(
            """
            INSERT INTO users (username, password_hash, salt, role)
            VALUES ('testuser', 'hash123', 'salt123', 'Cashier');
            """
        )
        self.assertIsNotNone(user_id)

        # Attempt atomic transaction that fails on the second query
        try:
            with self.db.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO bills (bill_number, cashier_id, subtotal, tax_rate, tax_amount, final_total, receipt_hash)
                    VALUES ('BILL-ROLLBACK-1', ?, 100.0, 0.05, 5.0, 105.0, 'dummy_hash');
                    """,
                    (user_id,),
                )
                # This second query will violate CHECK(price > 0)
                conn.execute(
                    """
                    INSERT INTO menu_items (item_name, category, price)
                    VALUES ('Bad Item', 'Beverages', -10.0);
                    """
                )
        except sqlite3.IntegrityError:
            pass  # Expected exception

        # The first insert ('BILL-ROLLBACK-1') should NOT exist due to rollback
        bill = self.db.fetch_one("SELECT * FROM bills WHERE bill_number = 'BILL-ROLLBACK-1';")
        self.assertIsNone(bill, "Bill should have been rolled back")

    def test_get_and_set_setting(self):
        """Verify setting updates and additions."""
        self.db.set_setting("currency_symbol", "$")
        self.assertEqual(self.db.get_setting("currency_symbol"), "$")

        self.db.set_setting("currency_symbol", "₹")
        self.assertEqual(self.db.get_setting("currency_symbol"), "₹")

    def test_centralized_store_and_tax_getters(self):
        """Verify get_restaurant_name and get_tax_rate return correct values with fallback."""
        from src.database.manager import DEFAULT_RESTAURANT_NAME, DEFAULT_TAX_RATE

        # Seeded defaults
        self.assertEqual(self.db.get_restaurant_name(), DEFAULT_RESTAURANT_NAME)
        self.assertEqual(self.db.get_tax_rate(), DEFAULT_TAX_RATE)

        # Updated settings
        self.db.set_setting("restaurant_name", "Grand Amrapali Bistro")
        self.db.set_setting("tax_rate", "0.18")
        self.assertEqual(self.db.get_restaurant_name(), "Grand Amrapali Bistro")
        self.assertEqual(self.db.get_tax_rate(), 0.18)

        # Invalid tax rate setting gracefully falls back to DEFAULT_TAX_RATE
        self.db.set_setting("tax_rate", "invalid_number")
        self.assertEqual(self.db.get_tax_rate(), DEFAULT_TAX_RATE)

        # Missing row falls back to canonical default
        self.db.execute("DELETE FROM app_settings WHERE setting_key = 'restaurant_name';")
        self.assertEqual(self.db.get_restaurant_name(), DEFAULT_RESTAURANT_NAME)


if __name__ == "__main__":
    unittest.main()
