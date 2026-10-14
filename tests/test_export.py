"""Unit Tests for PDF Invoicing and Data Export Subsystem
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)

Verifies:
1. ISO 32000-1 compliant vector PDF invoice generation (pure Python).
2. Excel-compatible UTF-8 BOM CSV exports for invoices and line items.
3. Structured JSON exports for invoices and menu catalog.
4. Role-based access control (RBAC) filtering and sensitive credential omission.
"""

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

from src.audit.logger import AuditLogger
from src.auth.service import AuthService
from src.billing.cart import OrderCart
from src.billing.exporter import ExportService, export_service
from src.billing.pdf_generator import generate_all_invoices_pdf, generate_invoice_pdf
from src.billing.service import BillingService
from src.database.manager import DatabaseManager


class TestDataExportAndPDF(unittest.TestCase):
    """Test suite covering PDF invoice rendering and multi-format data exports."""

    def setUp(self):
        """Provision isolated temporary test database with baseline schema."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db = DatabaseManager(self.temp_db.name)
        self.db.initialize_schema()

        self.audit = AuditLogger(db_manager=self.db)
        self.auth = AuthService(db_manager=self.db, audit_engine=self.audit)
        self.billing = BillingService(db_manager=self.db, audit_engine=self.audit)
        self.exporter = ExportService(db_manager=self.db, billing_engine=self.billing)

        # Setup Administrator & Cashiers
        self.auth.initial_setup_admin("admin", "AdminPass@2026", "MasterKey@Secret99")
        _, self.admin_session, _ = self.auth.login("admin", "AdminPass@2026")

        self.auth.create_staff_account(self.admin_session, "cashier1", "TempPass@1234")
        self.auth.change_user_password("cashier1", "TempPass@1234", "CashierOne@2026")
        _, self.cashier1_session, _ = self.auth.login("cashier1", "CashierOne@2026")

        self.auth.create_staff_account(self.admin_session, "cashier2", "TempPass@1234")
        self.auth.change_user_password("cashier2", "TempPass@1234", "CashierTwo@2026")
        _, self.cashier2_session, _ = self.auth.login("cashier2", "CashierTwo@2026")

        # Checkout test orders
        # Cashier 1 order
        cart1 = OrderCart()
        cart1.add_item(1, "Masala Chai", 30.00, quantity=2)  # 60
        cart1.add_item(3, "Paneer Tikka", 220.00, quantity=1)  # 220 -> Total 280
        ok1, self.bill1, _ = self.billing.checkout(
            self.cashier1_session, cart1, payment_mode="UPI", customer_phone_input="9876543210", discount_input=10.0
        )
        self.assertTrue(ok1)

        # Cashier 2 order
        cart2 = OrderCart()
        cart2.add_item(2, "Filter Coffee", 40.00, quantity=3)  # 120
        ok2, self.bill2, _ = self.billing.checkout(
            self.cashier2_session, cart2, payment_mode="Cash", customer_phone_input="9123456780"
        )
        self.assertTrue(ok2)

    def tearDown(self):
        """Clean up temporary test database."""
        try:
            if hasattr(self, "temp_db") and os.path.exists(self.temp_db.name):
                os.remove(self.temp_db.name)
        except OSError:
            pass

    def test_pure_python_vector_pdf_generation(self):
        """Verify vector PDF syntax conforming to ISO 32000-1 (PDF 1.4)."""
        det = self.billing.get_bill_details(self.bill1["bill_id"], decrypt_phone=True)
        self.assertIsNotNone(det)

        pdf_bytes = generate_invoice_pdf(det, restaurant_name="Amrapali Campus Diner")
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 500)

        # Validate PDF binary header and EOF trailer
        self.assertTrue(pdf_bytes.startswith(b"%PDF-1.4"), "PDF must have valid 1.4 version header")
        self.assertTrue(pdf_bytes.rstrip().endswith(b"%%EOF"), "PDF must terminate with %%EOF marker")

        # Validate structural elements
        self.assertIn(b"/Type /Catalog", pdf_bytes)
        self.assertIn(b"/Type /Pages", pdf_bytes)
        self.assertIn(b"/Type /Page", pdf_bytes)
        self.assertIn(b"/Font", pdf_bytes)
        self.assertIn(b"xref", pdf_bytes)
        self.assertIn(b"trailer", pdf_bytes)

        # Validate content text presence
        self.assertIn(det["bill_number"].encode("latin-1"), pdf_bytes)
        self.assertIn(b"AMRAPALI CAMPUS DINER", pdf_bytes)
        self.assertIn(b"Masala Chai", pdf_bytes)
        self.assertIn(b"Paneer Tikka", pdf_bytes)

    def test_export_invoice_to_pdf_file(self):
        """Verify exporter writes readable PDF file to disk."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "test_invoice.pdf"
            success, msg = self.exporter.export_invoice_to_pdf(self.bill1["bill_id"], pdf_path)
            self.assertTrue(success, msg)
            self.assertTrue(pdf_path.exists())
            self.assertGreater(pdf_path.stat().st_size, 500)

            # Test invalid bill ID
            fail, fail_msg = self.exporter.export_invoice_to_pdf(99999, pdf_path)
            self.assertFalse(fail)
            self.assertIn("not found", fail_msg)

    def test_invoices_registry_csv_export_and_excel_compatibility(self):
        """Verify UTF-8 BOM CSV invoice registry export and Excel readiness."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "invoices.csv"

            # Admin exports all invoices
            success, msg = self.exporter.export_invoices_to_csv(csv_path, session=self.admin_session)
            self.assertTrue(success, msg)
            self.assertTrue(csv_path.exists())

            # Verify UTF-8 BOM for Microsoft Excel compatibility
            with open(csv_path, "rb") as bf:
                header_bytes = bf.read(3)
                self.assertEqual(header_bytes, b"\xef\xbb\xbf", "CSV must contain UTF-8 BOM for Excel compatibility")

            # Parse CSV rows
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = list(csv.reader(f))
                self.assertGreaterEqual(len(reader), 3)  # Header + 2 bills

                headers = reader[0]
                self.assertIn("Invoice Number", headers)
                self.assertIn("Cashier Name", headers)
                self.assertIn("Subtotal (INR)", headers)
                self.assertIn("Final Total (INR)", headers)
                self.assertIn("Digital HMAC Checksum", headers)

                bill_numbers = [row[0] for row in reader[1:]]
                self.assertIn(self.bill1["bill_number"], bill_numbers)
                self.assertIn(self.bill2["bill_number"], bill_numbers)

            # Verify sensitive credentials (passwords, salts, master key) are NOT present
            with open(csv_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertNotIn("AdminPass@2026", content)
                self.assertNotIn("MasterKey@Secret99", content)
                self.assertNotIn("password_hash", content)

    def test_invoices_detailed_items_csv_export(self):
        """Verify detailed itemized breakdown export."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "line_items.csv"
            success, msg = self.exporter.export_invoice_items_to_csv(csv_path, session=self.admin_session)
            self.assertTrue(success, msg)

            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = list(csv.reader(f))
                self.assertGreaterEqual(len(reader), 4)  # Header + 3 line items across 2 bills

                headers = reader[0]
                self.assertIn("Invoice Number", headers)
                self.assertIn("Item Description", headers)
                self.assertIn("Quantity", headers)
                self.assertIn("Line Total (INR)", headers)

                descriptions = [row[3] for row in reader[1:]]
                self.assertIn("Masala Chai", descriptions)
                self.assertIn("Paneer Tikka", descriptions)
                self.assertIn("Filter Coffee", descriptions)

    def test_invoices_registry_json_export(self):
        """Verify structured JSON invoice registry export."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "invoices.json"
            success, msg = self.exporter.export_invoices_to_json(json_path, session=self.admin_session)
            self.assertTrue(success, msg)

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.assertEqual(data["export_type"], "invoices")
            self.assertEqual(data["record_count"], 2)
            self.assertEqual(len(data["invoices"]), 2)

            first_inv = data["invoices"][0]
            self.assertIn("bill_number", first_inv)
            self.assertIn("final_total", first_inv)
            self.assertIn("items", first_inv)
            self.assertIsInstance(first_inv["items"], list)

            # Ensure zero credential leak
            raw_text = json.dumps(data)
            self.assertNotIn("password", raw_text.lower())
            self.assertNotIn("salt", raw_text.lower())

    def test_menu_catalog_csv_and_json_export(self):
        """Verify menu catalog export to CSV and JSON."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "menu.csv"
            json_path = Path(tmp_dir) / "menu.json"

            # CSV
            ok_csv, msg_csv = self.exporter.export_menu_to_csv(csv_path)
            self.assertTrue(ok_csv, msg_csv)
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = list(csv.reader(f))
                self.assertGreaterEqual(len(reader), 5)  # Seed menu items
                self.assertEqual(reader[0][1], "Item Name")

            # JSON
            ok_json, msg_json = self.exporter.export_menu_to_json(json_path)
            self.assertTrue(ok_json, msg_json)
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["export_type"], "menu_catalog")
            self.assertGreater(data["item_count"], 0)
            self.assertIsInstance(data["items"], list)

    def test_rbac_cashier_shift_isolation(self):
        """Verify Cashier can only export their own shift bills, not other operators' invoices."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            c1_csv = Path(tmp_dir) / "cashier1_shift.csv"
            c2_csv = Path(tmp_dir) / "cashier2_shift.csv"

            # Cashier 1 exports
            ok1, _ = self.exporter.export_invoices_to_csv(c1_csv, session=self.cashier1_session)
            self.assertTrue(ok1)
            with open(c1_csv, "r", encoding="utf-8-sig") as f:
                c1_rows = list(csv.reader(f))[1:]
                self.assertEqual(len(c1_rows), 1)
                self.assertEqual(c1_rows[0][0], self.bill1["bill_number"])

            # Cashier 2 exports
            ok2, _ = self.exporter.export_invoices_to_csv(c2_csv, session=self.cashier2_session)
            self.assertTrue(ok2)
            with open(c2_csv, "r", encoding="utf-8-sig") as f:
                c2_rows = list(csv.reader(f))[1:]
                self.assertEqual(len(c2_rows), 1)
                self.assertEqual(c2_rows[0][0], self.bill2["bill_number"])

    def test_generate_all_invoices_multi_page_pdf(self):
        """Verify vector PDF compiles multiple invoices into a multi-page PDF document."""
        det1 = self.billing.get_bill_details(self.bill1["bill_id"], decrypt_phone=True)
        det2 = self.billing.get_bill_details(self.bill2["bill_id"], decrypt_phone=True)

        pdf_bytes = generate_all_invoices_pdf([det1, det2], restaurant_name="Amrapali Campus Diner")
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000)

        # Standard PDF checks
        self.assertTrue(pdf_bytes.startswith(b"%PDF-1.4"))
        self.assertTrue(pdf_bytes.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"/Type /Pages", pdf_bytes)
        self.assertIn(b"/Count 2", pdf_bytes)  # 2 Pages

        # Content presence from both invoices
        self.assertIn(det1["bill_number"].encode("latin-1"), pdf_bytes)
        self.assertIn(det2["bill_number"].encode("latin-1"), pdf_bytes)
        self.assertIn(b"Masala Chai", pdf_bytes)
        self.assertIn(b"Filter Coffee", pdf_bytes)

    def test_export_all_invoices_to_pdf_file_and_rbac(self):
        """Verify export_all_invoices_to_pdf writes multi-page file and respects cashier RBAC."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            admin_pdf_path = Path(tmp_dir) / "all_invoices_admin.pdf"
            c1_pdf_path = Path(tmp_dir) / "all_invoices_cashier1.pdf"

            # Admin exports all invoices
            ok_admin, msg_admin = self.exporter.export_all_invoices_to_pdf(admin_pdf_path, session=self.admin_session)
            self.assertTrue(ok_admin, msg_admin)
            self.assertTrue(admin_pdf_path.exists())
            self.assertGreater(admin_pdf_path.stat().st_size, 1000)

            with open(admin_pdf_path, "rb") as f:
                admin_pdf_bytes = f.read()
            self.assertIn(b"/Count 2", admin_pdf_bytes)
            self.assertIn(self.bill1["bill_number"].encode("latin-1"), admin_pdf_bytes)
            self.assertIn(self.bill2["bill_number"].encode("latin-1"), admin_pdf_bytes)

            # Cashier 1 exports shift invoices (only cashier 1's bills)
            ok_c1, msg_c1 = self.exporter.export_all_invoices_to_pdf(c1_pdf_path, session=self.cashier1_session)
            self.assertTrue(ok_c1, msg_c1)
            self.assertTrue(c1_pdf_path.exists())

            with open(c1_pdf_path, "rb") as f:
                c1_pdf_bytes = f.read()
            self.assertIn(b"/Count 1", c1_pdf_bytes)
            self.assertIn(self.bill1["bill_number"].encode("latin-1"), c1_pdf_bytes)
            self.assertNotIn(self.bill2["bill_number"].encode("latin-1"), c1_pdf_bytes)

    def test_export_all_invoices_empty_criteria(self):
        """Verify export returns helpful message when no invoices match criteria."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "empty.pdf"
            ok, msg = self.exporter.export_all_invoices_to_pdf(pdf_path, cashier_id=9999)
            self.assertFalse(ok)
            self.assertIn("No invoices found", msg)


if __name__ == "__main__":
    unittest.main()
