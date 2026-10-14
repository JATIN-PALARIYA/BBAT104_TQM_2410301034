"""Unit, Financial, and Security Tests for Billing & Invoicing Engine
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
from src.billing import BillingService, OrderCart
from src.database import DatabaseManager


class TestBillingEngine(unittest.TestCase):
    """Test suite covering cart logic, GST computation, atomic checkout, encryption, checksums, and voiding."""

    def setUp(self):
        """Create an isolated test database with users and menu items."""
        self.test_db_path = BASE_DIR / "tests" / "test_billing_scratch.db"
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        self.db = DatabaseManager(self.test_db_path)
        self.db.initialize_schema()
        self.audit = AuditLogger(self.db)
        self.billing = BillingService(self.db, self.audit)

        # Create Admin and Cashier in DB
        self.admin_id = self.db.execute(
            "INSERT INTO users (username, password_hash, salt, role) VALUES ('admin', 'h1', 's1', 'Admin');"
        )
        self.cashier_id = self.db.execute(
            "INSERT INTO users (username, password_hash, salt, role) VALUES ('cashier1', 'h2', 's2', 'Cashier');"
        )

        self.admin_session = UserSession(user_id=self.admin_id, username="admin", role="Admin", must_change_password=False)
        self.cashier_session = UserSession(user_id=self.cashier_id, username="cashier1", role="Cashier", must_change_password=False)

    def tearDown(self):
        """Clean up test database files."""
        if self.test_db_path.exists():
            try:
                self.test_db_path.unlink()
            except PermissionError:
                pass

    def test_cart_operations(self):
        """Verify cart addition, incrementation, and removals."""
        cart = OrderCart()
        self.assertTrue(cart.is_empty)

        # Add Masala Chai (₹30.00)
        success, _ = cart.add_item(1, "Masala Chai", 30.00, quantity=2)
        self.assertTrue(success)
        self.assertEqual(len(cart.items), 1)
        self.assertEqual(cart.items[0].quantity, 2)
        self.assertEqual(cart.items[0].line_total, 60.00)

        # Add more Masala Chai
        cart.add_item(1, "Masala Chai", 30.00, quantity=1)
        self.assertEqual(cart.items[0].quantity, 3)
        self.assertEqual(cart.items[0].line_total, 90.00)

        # Add Paneer Tikka (₹220.00)
        cart.add_item(3, "Paneer Tikka", 220.00, quantity=1)
        self.assertEqual(len(cart.items), 2)

        # Remove item
        cart.remove_item(1)
        self.assertEqual(len(cart.items), 1)
        self.assertEqual(cart.items[0].item_name, "Paneer Tikka")

    def test_financial_calculation_pipeline(self):
        """Verify exact math: Subtotal, Discount, 5% GST, and Grand Total."""
        cart = OrderCart()
        cart.add_item(1, "Masala Chai", 30.00, quantity=2)     # ₹60.00
        cart.add_item(3, "Paneer Tikka", 220.00, quantity=2)   # ₹440.00
        # Total Subtotal = ₹500.00

        # Case 1: No discount, 5% GST inclusive
        totals = cart.calculate_totals(discount_percent=0.0, tax_rate=0.05)
        self.assertEqual(totals["subtotal"], 500.00)
        self.assertEqual(totals["discount_amount"], 0.00)
        self.assertEqual(totals["final_total"], 500.00)
        self.assertEqual(totals["taxable_amount"], 476.19)  # 500 / 1.05
        self.assertEqual(totals["tax_amount"], 23.81)       # 500 - 476.19

        # Case 2: 10% discount, 5% GST inclusive
        totals = cart.calculate_totals(discount_percent=10.0, tax_rate=0.05)
        self.assertEqual(totals["subtotal"], 500.00)
        self.assertEqual(totals["discount_amount"], 50.00)  # 10% of 500
        self.assertEqual(totals["final_total"], 450.00)     # 500 - 50
        self.assertEqual(totals["taxable_amount"], 428.57)  # 450 / 1.05
        self.assertEqual(totals["tax_amount"], 21.43)       # 450 - 428.57

    def test_poka_yoke_empty_cart_checkout_rejected(self):
        """Verify empty cart cannot be checked out."""
        cart = OrderCart()
        success, _, msg = self.billing.checkout(self.cashier_session, cart)
        self.assertFalse(success)
        self.assertIn("Poka-Yoke", msg)

    def test_atomic_checkout_and_receipt_generation(self):
        """Verify atomic transaction, unique bill number, AES phone encryption, and HMAC checksum."""
        cart = OrderCart()
        cart.add_item(1, "Masala Chai", 30.00, quantity=2)
        cart.add_item(3, "Paneer Tikka", 220.00, quantity=1)

        success, bill, msg = self.billing.checkout(
            session=self.cashier_session,
            cart=cart,
            payment_mode="UPI",
            customer_phone_input="9876543210",
            discount_input=5.0,
        )
        self.assertTrue(success, msg)
        self.assertIsNotNone(bill)
        self.assertTrue(bill["bill_number"].startswith("BILL-"))
        self.assertTrue(cart.is_empty, "Cart must be cleared after successful checkout")

        # Verify receipt text formatting
        self.assertIn(bill["bill_number"], bill["receipt_text"])
        self.assertIn("Masala Chai", bill["receipt_text"])
        self.assertIn("Incl. GST (5%):", bill["receipt_text"])
        self.assertIn("Digital Checksum", bill["receipt_text"])

        # Verify database record and phone encryption at rest
        stored_bill = self.db.fetch_one("SELECT * FROM bills WHERE bill_id = ?;", (bill["bill_id"],))
        self.assertIsNotNone(stored_bill["customer_phone_enc"])
        self.assertNotEqual(stored_bill["customer_phone_enc"], "9876543210", "Phone must be encrypted at rest")

        # Verify decrypted retrieval
        details = self.billing.get_bill_details(bill["bill_id"], decrypt_phone=True)
        self.assertEqual(details["customer_phone"], "9876543210")
        self.assertEqual(len(details["items"]), 2)

        # Verify receipt signature
        valid, chk_msg = self.billing.verify_bill_integrity(bill["bill_id"])
        self.assertTrue(valid, chk_msg)

    def test_tamper_detection_on_bill_total(self):
        """Verify that altering a bill's total directly in SQLite breaks the digital signature."""
        cart = OrderCart()
        cart.add_item(1, "Masala Chai", 30.00, quantity=1)
        _, bill, _ = self.billing.checkout(self.cashier_session, cart)

        # Adversary alters bill final_total in the database
        self.db.execute("UPDATE bills SET final_total = 1.00 WHERE bill_id = ?;", (bill["bill_id"],))

        # Checksum verification must fail
        valid, chk_msg = self.billing.verify_bill_integrity(bill["bill_id"])
        self.assertFalse(valid)
        self.assertIn("mismatch", chk_msg)

    def test_controlled_bill_voiding(self):
        """Verify Admin can void a bill with mandatory reason, and Cashier cannot."""
        cart = OrderCart()
        cart.add_item(1, "Masala Chai", 30.00, quantity=1)
        _, bill, _ = self.billing.checkout(self.cashier_session, cart)

        # Cashier tries to void -> REJECTED (RBAC)
        success, msg = self.billing.void_bill(self.cashier_session, bill["bill_id"], "Customer left without paying")
        self.assertFalse(success)
        self.assertIn("Access Denied", msg)

        # Admin tries to void without reason -> REJECTED (Poka-Yoke)
        success, msg = self.billing.void_bill(self.admin_session, bill["bill_id"], "")
        self.assertFalse(success)
        self.assertIn("Poka-Yoke", msg)

        # Admin voids with valid reason -> SUCCESS
        success, msg = self.billing.void_bill(self.admin_session, bill["bill_id"], "Order canceled by guest")
        self.assertTrue(success, msg)

        # Verify bill status is VOID
        voided_bill = self.db.fetch_one("SELECT * FROM bills WHERE bill_id = ?;", (bill["bill_id"],))
        self.assertEqual(voided_bill["status"], "VOID")
        self.assertEqual(voided_bill["void_reason"], "Order canceled by guest")

    def test_get_receipt_text_for_bill(self):
        """Verify historical receipt reconstruction for active, voided, and missing bills."""
        # Non-existent bill
        self.assertIsNone(self.billing.get_receipt_text_for_bill(999999))

        # Create a bill with customer phone and discount
        cart = OrderCart()
        cart.add_item(1, "Masala Chai", 30.00, quantity=2)
        cart.add_item(3, "Paneer Tikka", 220.00, quantity=1)
        success, bill, _ = self.billing.checkout(
            self.cashier_session,
            cart,
            customer_phone_input="9876543210",
            payment_mode="Card",
            discount_input=10.0,
        )
        self.assertTrue(success)

        # Retrieve receipt text for active bill
        receipt_text = self.billing.get_receipt_text_for_bill(bill["bill_id"])
        self.assertIsNotNone(receipt_text)
        self.assertIn("Bill No :", receipt_text)
        self.assertIn("Masala Chai", receipt_text)
        self.assertIn("Paneer Tikka", receipt_text)
        self.assertIn("Customer: +91 987***3210", receipt_text)
        self.assertIn("Payment : Card", receipt_text)
        self.assertIn("Discount (10%):", receipt_text)
        self.assertNotIn("*** VOIDED INVOICE ***", receipt_text)

        # Void the bill and verify receipt text updates to show VOID banner and reason
        self.billing.void_bill(self.admin_session, bill["bill_id"], "Customer changed mind")
        void_receipt_text = self.billing.get_receipt_text_for_bill(bill["bill_id"])
        self.assertIsNotNone(void_receipt_text)
        self.assertIn("*** VOIDED INVOICE:", void_receipt_text)
        self.assertIn("Customer changed mind", void_receipt_text)


    def test_custom_tax_rate_admin_configuration(self):
        """Verify that Admin can customize the tax rate (e.g. 5% to 18% GST) with RBAC and Poka-Yoke guards."""
        # 1. Verify default tax rate is 0.05 (5%)
        self.assertEqual(self.billing.get_tax_rate(), 0.05)

        # 2. Cashier attempting to change tax rate must be blocked
        success, msg = self.billing.update_tax_rate(self.cashier_session, 0.18)
        self.assertFalse(success)
        self.assertIn("Access Denied", msg)

        # 3. Poka-Yoke bounds validation on tax rate (must be 0.0 to 0.50)
        success, msg = self.billing.update_tax_rate(self.admin_session, -0.05)
        self.assertFalse(success)
        self.assertIn("Poka-Yoke Rejection", msg)

        success, msg = self.billing.update_tax_rate(self.admin_session, 0.85)
        self.assertFalse(success)
        self.assertIn("Poka-Yoke Rejection", msg)

        # 4. Admin successfully updates tax rate to 18% GST (0.18)
        success, msg = self.billing.update_tax_rate(self.admin_session, 0.18)
        self.assertTrue(success, msg)
        self.assertEqual(self.billing.get_tax_rate(), 0.18)

        # 5. Verify subsequent bill uses the updated 18% tax rate
        cart = OrderCart()
        cart.add_item(item_id=1, item_name="Masala Chai", unit_price=100.0, quantity=1)
        # For 100.0 subtotal at 18% GST:
        # Final Total = 100.0, Taxable = 100 / 1.18 = 84.75, Tax = 15.25
        success, bill, msg = self.billing.checkout(
            session=self.cashier_session,
            cart=cart,
            payment_mode="Cash",
        )
        self.assertTrue(success, msg)
        self.assertEqual(bill["tax_rate"], 0.18)
        self.assertAlmostEqual(bill["final_total"], 100.0, places=2)


if __name__ == "__main__":
    unittest.main()
