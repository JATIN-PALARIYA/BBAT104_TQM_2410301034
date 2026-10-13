"""Unit and Security Tests for Audit Trail Hash Chaining & Tamper Detection
Restaurant Billing System [Q04: Improve Security] - BBAT104
Student: Jatin Palariya (Roll No: 2410301034)
"""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.audit import GENESIS_HASH, AuditLogger
from src.database import DatabaseManager


class TestAuditTrail(unittest.TestCase):
    """Test suite covering event logging, cryptographic SHA-256 hash-chaining, and tamper detection."""

    def setUp(self):
        """Create an isolated temporary database for audit tests."""
        self.test_db_path = BASE_DIR / "tests" / "test_audit_scratch.db"
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        self.db = DatabaseManager(self.test_db_path)
        self.db.initialize_schema()
        self.audit = AuditLogger(self.db)

    def tearDown(self):
        """Clean up test database files."""
        if self.test_db_path.exists():
            try:
                self.test_db_path.unlink()
            except PermissionError:
                pass

    def test_empty_audit_trail_is_valid(self):
        """Verify that an empty audit log evaluates as valid."""
        result = self.audit.verify_audit_integrity()
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["total_records"], 0)

    def test_genesis_record_hash_chain(self):
        """Verify that the first audit log row references the GENESIS_HASH."""
        log_id = self.audit.log_event("USER_LOGIN_SUCCESS", "admin", "Admin logged in successfully", user_id=1)
        self.assertEqual(log_id, 1)

        logs = self.audit.get_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["prev_hash"], GENESIS_HASH)
        self.assertIsNotNone(logs[0]["record_hash"])

        result = self.audit.verify_audit_integrity()
        self.assertTrue(result["is_valid"])

    def test_multi_event_unbroken_chain(self):
        """Verify that multiple consecutive events maintain an unbroken hash chain."""
        id1 = self.audit.log_event("USER_LOGIN_SUCCESS", "admin", "Admin login", user_id=1)
        id2 = self.audit.log_event("MENU_ITEM_ADDED", "admin", "Added Paneer Butter Masala", user_id=1)
        id3 = self.audit.log_event("BILL_GENERATED", "cashier1", "Bill BILL-20261011-0001 created", user_id=2)
        id4 = self.audit.log_event("USER_LOGOUT", "admin", "Admin logged out", user_id=1)

        logs = self.audit.get_logs(limit=10)
        self.assertEqual(len(logs), 4)

        # Logs are returned in reverse order: [id4, id3, id2, id1]
        self.assertEqual(logs[0]["log_id"], id4)
        self.assertEqual(logs[1]["log_id"], id3)
        self.assertEqual(logs[2]["log_id"], id2)
        self.assertEqual(logs[3]["log_id"], id1)

        # Verify links: id4 prev_hash == id3 record_hash
        self.assertEqual(logs[0]["prev_hash"], logs[1]["record_hash"])
        self.assertEqual(logs[1]["prev_hash"], logs[2]["record_hash"])
        self.assertEqual(logs[2]["prev_hash"], logs[3]["record_hash"])
        self.assertEqual(logs[3]["prev_hash"], GENESIS_HASH)

        verification = self.audit.verify_audit_integrity()
        self.assertTrue(verification["is_valid"])
        self.assertEqual(verification["total_records"], 4)
        self.assertEqual(len(verification["corrupted_records"]), 0)

    def test_tamper_detection_modified_content(self):
        """Verify that modifying a record's details directly in SQLite is detected."""
        self.audit.log_event("USER_LOGIN_SUCCESS", "admin", "Login event 1", user_id=1)
        self.audit.log_event("BILL_GENERATED", "cashier", "Bill 101 generated: ₹500", user_id=2)
        self.audit.log_event("BILL_VOIDED", "admin", "Bill 101 voided: customer dispute", user_id=1)

        # Adversary modifies row 2 details directly in the SQLite database
        self.db.execute("UPDATE audit_logs SET details = 'HACKED DETAILS: ₹0' WHERE log_id = 2;")

        # Verification must flag row 2 as corrupted
        result = self.audit.verify_audit_integrity()
        self.assertFalse(result["is_valid"], "Tampered database must fail integrity verification")
        self.assertIn(2, result["corrupted_records"])

    def test_tamper_detection_deleted_record(self):
        """Verify that deleting an intermediate log record is detected."""
        self.audit.log_event("USER_LOGIN_SUCCESS", "admin", "Event 1", user_id=1)
        self.audit.log_event("MENU_ITEM_ADDED", "admin", "Event 2", user_id=1)
        self.audit.log_event("USER_LOGOUT", "admin", "Event 3", user_id=1)

        # Adversary deletes row 2 to hide an action
        self.db.execute("DELETE FROM audit_logs WHERE log_id = 2;")

        # Verification must flag the sequence gap and broken prev_hash link
        result = self.audit.verify_audit_integrity()
        self.assertFalse(result["is_valid"])
        self.assertIn(3, result["corrupted_records"])

    def test_invalid_action_type_rejected(self):
        """Verify that unsupported action types raise ValueError."""
        with self.assertRaises(ValueError):
            self.audit.log_event("MALICIOUS_CUSTOM_ACTION", "hacker", "Attempted backdoor")

    def test_get_total_logs_count_and_pagination(self):
        """Verify get_total_logs_count and paginated retrieval in batches of 10."""
        # 0 records initially
        self.assertEqual(self.audit.get_total_logs_count(), 0)
        empty_batch = self.audit.get_logs(limit=10, offset=0)
        self.assertEqual(len(empty_batch), 0)

        # Log 25 distinct events
        for i in range(1, 26):
            self.audit.log_event("USER_LOGIN_SUCCESS", "admin", f"Login event #{i}", user_id=1)

        # Count must be exactly 25
        self.assertEqual(self.audit.get_total_logs_count(), 25)

        # Page 1: records 25 down to 16 (10 records)
        page1 = self.audit.get_logs(limit=10, offset=0)
        self.assertEqual(len(page1), 10)
        self.assertEqual(page1[0]["log_id"], 25)
        self.assertEqual(page1[-1]["log_id"], 16)

        # Page 2: records 15 down to 6 (10 records)
        page2 = self.audit.get_logs(limit=10, offset=10)
        self.assertEqual(len(page2), 10)
        self.assertEqual(page2[0]["log_id"], 15)
        self.assertEqual(page2[-1]["log_id"], 6)

        # Page 3: records 5 down to 1 (5 records)
        page3 = self.audit.get_logs(limit=10, offset=20)
        self.assertEqual(len(page3), 5)
        self.assertEqual(page3[0]["log_id"], 5)
        self.assertEqual(page3[-1]["log_id"], 1)

        # Page 4: beyond total records returns empty list
        page4 = self.audit.get_logs(limit=10, offset=30)
        self.assertEqual(len(page4), 0)


if __name__ == "__main__":
    unittest.main()
