"""Data Export Service (PDF, CSV, Excel-compatible, and JSON)
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)

Provides role-aware, tamper-evident export pipelines for customer invoices,
shift billing logs, and menu catalogs without external dependencies.
Strictly excludes encryption keys, passwords, salts, and secret parameters.
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.auth.session import UserSession
from src.billing.pdf_generator import generate_all_invoices_pdf, generate_invoice_pdf
from src.billing.service import billing_service
from src.database import db
from src.menu.service import MenuService, menu_service


class ExportService:
    """Manages role-enforced exports to PDF, CSV (Excel-compatible), and JSON."""

    def __init__(self, db_manager=None, billing_engine=None, menu_engine=None):
        self.db = db_manager or db
        self.billing = billing_engine or billing_service
        self.menu = menu_engine or (menu_service if db_manager is None else MenuService(db_manager=self.db))

    # =========================================================================
    # 1. Individual Invoice PDF Export
    # =========================================================================
    def export_invoice_to_pdf(self, bill_id: int, target_path: str | Path) -> Tuple[bool, str]:
        """Generate and save a professional vector PDF for a specific invoice."""
        det = self.billing.get_bill_details(bill_id, decrypt_phone=True)
        if not det:
            return False, f"Invoice with ID {bill_id} not found."

        try:
            store_name = self.db.get_restaurant_name()
            pdf_bytes = generate_invoice_pdf(det, restaurant_name=store_name)

            path = Path(target_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                f.write(pdf_bytes)

            return True, f"Invoice {det['bill_number']} successfully saved to:\n{path.resolve()}"
        except Exception as e:
            return False, f"Failed to generate invoice PDF: {str(e)}"

    def export_all_invoices_to_pdf(
        self,
        target_path: str | Path,
        cashier_id: Optional[int] = None,
        session: Optional[UserSession] = None,
    ) -> Tuple[bool, str]:
        """Export all invoices (or cashier-specific shift invoices) to a consolidated multi-page PDF.

        Enforces RBAC: Cashiers can only export their own shift invoices.
        """
        effective_cashier_id = cashier_id
        if session and session.is_cashier():
            effective_cashier_id = session.user_id

        bills = self.billing.get_bill_history(cashier_id=effective_cashier_id)
        if not bills:
            return False, "No invoices found matching the export criteria."

        detailed_bills = []
        for b in bills:
            det = self.billing.get_bill_details(b["bill_id"], decrypt_phone=True)
            if det:
                detailed_bills.append(det)

        if not detailed_bills:
            return False, "Failed to retrieve invoice details for PDF export."

        try:
            store_name = self.db.get_restaurant_name()
            pdf_bytes = generate_all_invoices_pdf(detailed_bills, restaurant_name=store_name)

            path = Path(target_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                f.write(pdf_bytes)

            return True, f"Successfully exported {len(detailed_bills)} invoice(s) as PDF to:\n{path.resolve()}"
        except Exception as e:
            return False, f"Failed to export all invoices to PDF: {str(e)}"

    # =========================================================================
    # 2. Invoices Registry CSV / Excel Export
    # =========================================================================
    def export_invoices_to_csv(
        self,
        target_path: str | Path,
        cashier_id: Optional[int] = None,
        session: Optional[UserSession] = None,
    ) -> Tuple[bool, str]:
        """Export invoice transaction headers to Excel-compatible UTF-8 CSV.

        Enforces RBAC: Cashiers can only export their own shift invoices.
        """
        # RBAC Check
        effective_cashier_id = cashier_id
        if session and session.is_cashier():
            effective_cashier_id = session.user_id

        bills = self.billing.get_bill_history(cashier_id=effective_cashier_id)
        if not bills:
            return False, "No invoices found matching the export criteria."

        try:
            path = Path(target_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Use utf-8-sig (UTF-8 with BOM) so Microsoft Excel natively recognizes encoding
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Invoice Number",
                    "Date & Time",
                    "Cashier Name",
                    "Payment Mode",
                    "Status",
                    "Subtotal (INR)",
                    "Discount Amount (INR)",
                    "Tax Rate",
                    "GST Included (INR)",
                    "Final Total (INR)",
                    "Digital HMAC Checksum",
                    "Void Reason",
                ])

                for b in bills:
                    writer.writerow([
                        b["bill_number"],
                        b["created_at"],
                        b["cashier_name"],
                        b["payment_mode"],
                        b["status"],
                        f"{b['subtotal']:.2f}",
                        f"{b['discount_amount']:.2f}",
                        f"{b['tax_rate']:.2f}",
                        f"{b['tax_amount']:.2f}",
                        f"{b['final_total']:.2f}",
                        b.get("receipt_hash", "N/A"),
                        b.get("void_reason") or "",
                    ])

            return True, f"Successfully exported {len(bills)} invoice(s) to:\n{path.resolve()}"
        except Exception as e:
            return False, f"Failed to export invoices CSV: {str(e)}"

    # =========================================================================
    # 3. Detailed Line-Items CSV Export
    # =========================================================================
    def export_invoice_items_to_csv(
        self,
        target_path: str | Path,
        cashier_id: Optional[int] = None,
        session: Optional[UserSession] = None,
    ) -> Tuple[bool, str]:
        """Export granular itemized lines for all invoices (for inventory audit)."""
        effective_cashier_id = cashier_id
        if session and session.is_cashier():
            effective_cashier_id = session.user_id

        query = """
            SELECT
                b.bill_number,
                b.created_at,
                u.username AS cashier_name,
                bi.item_name_snapshot,
                bi.quantity,
                bi.unit_price_snapshot,
                bi.line_total,
                b.payment_mode,
                b.status
            FROM bill_items bi
            JOIN bills b ON bi.bill_id = b.bill_id
            JOIN users u ON b.cashier_id = u.user_id
        """
        params = []
        if effective_cashier_id is not None:
            query += " WHERE b.cashier_id = ?"
            params.append(effective_cashier_id)

        query += " ORDER BY b.bill_id ASC, bi.item_line_id ASC;"
        rows = self.db.fetch_all(query, tuple(params))

        if not rows:
            return False, "No line-item records found to export."

        try:
            path = Path(target_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Invoice Number",
                    "Date & Time",
                    "Cashier Name",
                    "Item Description",
                    "Quantity",
                    "Unit Rate (INR)",
                    "Line Total (INR)",
                    "Payment Mode",
                    "Invoice Status",
                ])

                for r in rows:
                    writer.writerow([
                        r["bill_number"],
                        r["created_at"],
                        r["cashier_name"],
                        r["item_name_snapshot"],
                        r["quantity"],
                        f"{r['unit_price_snapshot']:.2f}",
                        f"{r['line_total']:.2f}",
                        r["payment_mode"],
                        r["status"],
                    ])

            return True, f"Successfully exported {len(rows)} item line(s) to:\n{path.resolve()}"
        except Exception as e:
            return False, f"Failed to export line items CSV: {str(e)}"

    # =========================================================================
    # 4. Invoices Registry JSON Export
    # =========================================================================
    def export_invoices_to_json(
        self,
        target_path: str | Path,
        cashier_id: Optional[int] = None,
        session: Optional[UserSession] = None,
    ) -> Tuple[bool, str]:
        """Export invoices with nested line-items to structured JSON."""
        effective_cashier_id = cashier_id
        if session and session.is_cashier():
            effective_cashier_id = session.user_id

        bills = self.billing.get_bill_history(cashier_id=effective_cashier_id)
        if not bills:
            return False, "No invoices found matching the export criteria."

        full_records = []
        for b in bills:
            det = self.billing.get_bill_details(b["bill_id"], decrypt_phone=False)
            if det:
                # Remove sensitive internal ciphertexts or salts
                clean_det = {
                    "bill_number": det["bill_number"],
                    "created_at": det["created_at"],
                    "cashier_name": det["cashier_name"],
                    "payment_mode": det["payment_mode"],
                    "status": det["status"],
                    "subtotal": det["subtotal"],
                    "discount_amount": det["discount_amount"],
                    "tax_rate": det["tax_rate"],
                    "tax_amount": det["tax_amount"],
                    "final_total": det["final_total"],
                    "receipt_hash": det["receipt_hash"],
                    "void_reason": det.get("void_reason"),
                    "items": [
                        {
                            "item_name": itm["item_name_snapshot"],
                            "quantity": itm["quantity"],
                            "unit_price": itm["unit_price_snapshot"],
                            "line_total": itm["line_total"],
                        }
                        for itm in det.get("items", [])
                    ],
                }
                full_records.append(clean_det)

        try:
            path = Path(target_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "export_type": "invoices",
                        "restaurant_name": self.db.get_restaurant_name(),
                        "exported_at": str(Path(target_path).stat().st_mtime if Path(target_path).exists() else ""),
                        "record_count": len(full_records),
                        "invoices": full_records,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            return True, f"Successfully exported {len(full_records)} invoice(s) to:\n{path.resolve()}"
        except Exception as e:
            return False, f"Failed to export invoices JSON: {str(e)}"

    # =========================================================================
    # 5. Menu Catalog Export (CSV & JSON)
    # =========================================================================
    def export_menu_to_csv(self, target_path: str | Path) -> Tuple[bool, str]:
        """Export menu catalog to Excel-compatible UTF-8 CSV."""
        items = self.menu.get_all_menu_items(active_only=False)
        if not items:
            return False, "No menu items found to export."

        try:
            path = Path(target_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Item ID",
                    "Item Name",
                    "Category",
                    "Price (INR)",
                    "Status",
                    "Created At",
                    "Last Updated",
                ])
                for itm in items:
                    st = "Active" if itm["is_active"] else "Inactive"
                    writer.writerow([
                        itm["item_id"],
                        itm["item_name"],
                        itm["category"],
                        f"{itm['price']:.2f}",
                        st,
                        itm.get("created_at", ""),
                        itm.get("updated_at", ""),
                    ])

            return True, f"Successfully exported {len(items)} menu item(s) to:\n{path.resolve()}"
        except Exception as e:
            return False, f"Failed to export menu CSV: {str(e)}"

    def export_menu_to_json(self, target_path: str | Path) -> Tuple[bool, str]:
        """Export menu catalog to structured JSON."""
        items = self.menu.get_all_menu_items(active_only=False)
        if not items:
            return False, "No menu items found to export."

        cleaned_items = [
            {
                "item_id": itm["item_id"],
                "item_name": itm["item_name"],
                "category": itm["category"],
                "price": itm["price"],
                "is_active": bool(itm["is_active"]),
                "created_at": itm.get("created_at"),
                "updated_at": itm.get("updated_at"),
            }
            for itm in items
        ]

        try:
            path = Path(target_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "export_type": "menu_catalog",
                        "restaurant_name": self.db.get_restaurant_name(),
                        "item_count": len(cleaned_items),
                        "items": cleaned_items,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            return True, f"Successfully exported {len(cleaned_items)} menu item(s) to:\n{path.resolve()}"
        except Exception as e:
            return False, f"Failed to export menu JSON: {str(e)}"


# Default singleton instance
export_service = ExportService()
