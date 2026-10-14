"""Transactional Billing, Invoicing & Voiding Service [Q04: Security Core]
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.audit import audit_logger
from src.auth import UserSession
from src.billing.cart import CartItem, OrderCart
from src.billing.receipt import generate_receipt_text
from src.database import db
from src.security import (
    decrypt_customer_phone,
    encrypt_customer_phone,
    generate_receipt_checksum,
    sanitize_string,
    validate_customer_phone,
    validate_discount_percent,
    verify_receipt_checksum,
)


class BillingService:
    """Coordinates invoice creation, atomic transactions, receipt rendering, and voiding."""

    def __init__(self, db_manager=None, audit_engine=None):
        self.db = db_manager or db
        self.audit = audit_engine or audit_logger

    def _generate_next_bill_number(self, conn) -> str:
        """Generate unique daily bill number format: BILL-YYYYMMDD-XXXX."""
        today_str = datetime.now().strftime("%Y%m%d")
        prefix = f"BILL-{today_str}-"
        cursor = conn.execute(
            "SELECT bill_number FROM bills WHERE bill_number LIKE ? ORDER BY bill_id DESC LIMIT 1;",
            (f"{prefix}%",),
        )
        row = cursor.fetchone()
        if row:
            last_seq = int(row["bill_number"].split("-")[-1])
            next_seq = last_seq + 1
        else:
            next_seq = 1
        return f"{prefix}{next_seq:04d}"

    def checkout(
        self,
        session: UserSession,
        cart: OrderCart,
        payment_mode: str = "Cash",
        customer_phone_input: Optional[str] = None,
        discount_input: float = 0.0,
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Finalize bill in an atomic transaction, encrypt phone at rest, and generate receipt."""
        if not session:
            return False, None, "Access Denied: Unauthenticated checkout request."

        if cart.is_empty:
            return False, None, "Poka-Yoke Rejection: Cannot checkout an empty cart."

        # Validate payment mode
        if payment_mode not in ("Cash", "Card", "UPI"):
            return False, None, "Invalid payment mode. Supported modes: Cash, Card, UPI."

        # Validate discount percentage (0% to 20%)
        d_valid, discount_percent, d_msg = validate_discount_percent(discount_input)
        if not d_valid:
            return False, None, f"Poka-Yoke Rejection: {d_msg}"

        # Validate optional customer phone
        p_valid, clean_phone, p_msg = validate_customer_phone(customer_phone_input)
        if not p_valid:
            return False, None, f"Poka-Yoke Rejection: {p_msg}"

        # Encrypt phone number using AES-Fernet for storage at rest
        phone_ciphertext = encrypt_customer_phone(clean_phone)

        # Retrieve system tax rate setting
        tax_rate = self.db.get_tax_rate()

        totals = cart.calculate_totals(discount_percent=discount_percent, tax_rate=tax_rate)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.db.transaction() as conn:
            bill_number = self._generate_next_bill_number(conn)
            receipt_hash = generate_receipt_checksum(bill_number, now_str, totals["final_total"])

            # 1. Insert bill header
            cursor = conn.execute(
                """
                INSERT INTO bills (
                    bill_number, cashier_id, customer_phone_enc, subtotal, tax_rate,
                    tax_amount, discount_amount, final_total, payment_mode, status,
                    receipt_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED', ?, ?);
                """,
                (
                    bill_number,
                    session.user_id,
                    phone_ciphertext,
                    totals["subtotal"],
                    totals["tax_rate"],
                    totals["tax_amount"],
                    totals["discount_amount"],
                    totals["final_total"],
                    payment_mode,
                    receipt_hash,
                    now_str,
                ),
            )
            bill_id = cursor.lastrowid

            # 2. Insert line items snapshotting prices and names
            for item in cart.items:
                conn.execute(
                    """
                    INSERT INTO bill_items (
                        bill_id, menu_item_id, item_name_snapshot,
                        unit_price_snapshot, quantity, line_total
                    ) VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        bill_id,
                        item.item_id,
                        item.item_name,
                        item.unit_price,
                        item.quantity,
                        item.line_total,
                    ),
                )

            # 3. Log event in audit trail
            self.audit.log_event(
                "BILL_GENERATED",
                session.username,
                f"Generated {bill_number} (Total: ₹{totals['final_total']:.2f}, Mode: {payment_mode})",
                user_id=session.user_id,
                custom_time=now_str,
                conn=conn,
            )

        # Generate formatted printable receipt
        store_name = self.db.get_restaurant_name()
        receipt_text = generate_receipt_text(
            store_name=store_name,
            bill_number=bill_number,
            created_at=now_str,
            cashier_name=session.username,
            items=[{"name": i.item_name, "qty": i.quantity, "rate": i.unit_price, "total": i.line_total} for i in cart.items],
            totals=totals,
            payment_mode=payment_mode,
            customer_phone=clean_phone,
            receipt_hash=receipt_hash,
        )

        bill_summary = {
            "bill_id": bill_id,
            "bill_number": bill_number,
            "created_at": now_str,
            "tax_rate": totals["tax_rate"],
            "subtotal": totals["subtotal"],
            "tax_amount": totals["tax_amount"],
            "final_total": totals["final_total"],
            "receipt_text": receipt_text,
            "receipt_hash": receipt_hash,
        }

        # Clear active cart after successful write
        cart.clear()
        return True, bill_summary, f"Bill {bill_number} generated successfully."

    def generate_receipt_text(
        self,
        bill_number: str,
        created_at: str,
        cashier_name: str,
        items: List[Dict[str, Any]],
        totals: Dict[str, float],
        payment_mode: str,
        customer_phone: Optional[str],
        receipt_hash: str,
    ) -> str:
        """Instance method for receipt generation to maintain backward compatibility."""
        store_name = self.db.get_restaurant_name()
        return generate_receipt_text(
            store_name=store_name,
            bill_number=bill_number,
            created_at=created_at,
            cashier_name=cashier_name,
            items=items,
            totals=totals,
            payment_mode=payment_mode,
            customer_phone=customer_phone,
            receipt_hash=receipt_hash,
        )

    def get_bill_history(self, limit: int = 50, cashier_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve historical invoices. Cashiers only see their shift; Admins see all."""
        query = """
            SELECT b.bill_id, b.bill_number, b.cashier_id, u.username AS cashier_name,
                   b.subtotal, b.tax_rate, b.tax_amount, b.discount_amount, b.final_total,
                   b.payment_mode, b.status, b.void_reason, b.receipt_hash, b.created_at
            FROM bills b
            JOIN users u ON b.cashier_id = u.user_id
        """
        params: List[Any] = []
        if cashier_id is not None:
            query += " WHERE b.cashier_id = ?"
            params.append(cashier_id)

        query += " ORDER BY b.bill_id DESC LIMIT ?;"
        params.append(limit)

        rows = self.db.fetch_all(query, tuple(params))
        return [dict(r) for r in rows]

    def get_bill_details(self, bill_id: int, decrypt_phone: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch complete bill header, line items, and optionally decrypted customer phone."""
        bill_row = self.db.fetch_one(
            """
            SELECT b.*, u.username AS cashier_name
            FROM bills b
            JOIN users u ON b.cashier_id = u.user_id
            WHERE b.bill_id = ?;
            """,
            (bill_id,),
        )
        if not bill_row:
            return None

        bill_dict = dict(bill_row)
        if decrypt_phone and bill_dict.get("customer_phone_enc"):
            bill_dict["customer_phone"] = decrypt_customer_phone(bill_dict["customer_phone_enc"])
        else:
            bill_dict["customer_phone"] = "[Encrypted at Rest]"

        items = self.db.fetch_all(
            """
            SELECT item_line_id, menu_item_id, item_name_snapshot, unit_price_snapshot, quantity, line_total
            FROM bill_items
            WHERE bill_id = ?
            ORDER BY item_line_id ASC;
            """,
            (bill_id,),
        )
        bill_dict["items"] = [dict(i) for i in items]
        return bill_dict

    def get_receipt_text_for_bill(self, bill_id: int) -> Optional[str]:
        """Reconstruct the formatted itemized printable receipt for a historical bill.

        Preserves historical snapshot item descriptions, unit rates, quantities,
        subtotal, discounts, GST tax rate, grand total, payment mode, void status,
        and decrypted customer phone.
        """
        det = self.get_bill_details(bill_id, decrypt_phone=True)
        if not det:
            return None

        store_name = self.db.get_restaurant_name()
        items = [
            {
                "name": item["item_name_snapshot"],
                "qty": item["quantity"],
                "rate": item["unit_price_snapshot"],
                "total": item["line_total"],
            }
            for item in det["items"]
        ]

        subtotal = det["subtotal"]
        discount_amount = det["discount_amount"]
        discount_percent = (discount_amount / subtotal * 100.0) if subtotal > 0 and discount_amount > 0 else 0.0
        taxable_amount = max(0.0, subtotal - discount_amount)

        totals = {
            "subtotal": subtotal,
            "discount_percent": round(discount_percent, 2),
            "discount_amount": discount_amount,
            "taxable_amount": round(taxable_amount, 2),
            "tax_rate": det.get("tax_rate", 0.05),
            "tax_amount": det["tax_amount"],
            "final_total": det["final_total"],
        }

        phone = det.get("customer_phone")
        if phone == "[Encrypted at Rest]":
            phone = None

        receipt_text = generate_receipt_text(
            store_name=store_name,
            bill_number=det["bill_number"],
            created_at=det["created_at"],
            cashier_name=det["cashier_name"],
            items=items,
            totals=totals,
            payment_mode=det["payment_mode"],
            customer_phone=phone,
            receipt_hash=det.get("receipt_hash") or "N/A",
        )

        if det.get("status") == "VOID":
            void_reason = det.get("void_reason") or "N/A"
            receipt_text = f"*** VOIDED INVOICE: {void_reason} ***\n" + receipt_text

        return receipt_text

    def void_bill(self, admin_session: UserSession, bill_id: int, void_reason: str) -> Tuple[bool, str]:
        """Admin marks a finalized bill as VOID with mandatory cancellation reason."""
        if not admin_session or not admin_session.is_admin():
            return False, "Access Denied: Only Administrators have authorization to void bills."

        void_reason = sanitize_string(void_reason, 200)
        if not void_reason or len(void_reason) < 4:
            return False, "Poka-Yoke Rejection: A mandatory cancellation reason must be provided (min 4 chars)."

        bill = self.db.fetch_one("SELECT * FROM bills WHERE bill_id = ?;", (bill_id,))
        if not bill:
            return False, f"Bill #{bill_id} not found."

        if bill["status"] == "VOID":
            return False, f"Bill #{bill['bill_number']} is already marked as VOID."

        self.db.execute(
            """
            UPDATE bills SET
                status = 'VOID',
                void_reason = ?
            WHERE bill_id = ?;
            """,
            (void_reason, bill_id),
        )

        self.audit.log_event(
            "BILL_VOIDED",
            admin_session.username,
            f"Voided {bill['bill_number']} (Total: ₹{bill['final_total']:.2f}). Reason: {void_reason}",
            user_id=admin_session.user_id,
        )
        return True, f"Bill {bill['bill_number']} has been successfully marked VOID."

    def verify_bill_integrity(self, bill_id: int) -> Tuple[bool, str]:
        """Verify the stored HMAC digital checksum of a bill."""
        bill = self.db.fetch_one("SELECT * FROM bills WHERE bill_id = ?;", (bill_id,))
        if not bill:
            return False, "Bill not found."

        is_valid = verify_receipt_checksum(
            bill_number=bill["bill_number"],
            created_at=bill["created_at"],
            final_total=bill["final_total"],
            stored_checksum=bill["receipt_hash"],
        )

        if is_valid:
            return True, f"Receipt checksum verified for {bill['bill_number']}: Digital signature matches."
        return False, f"ALERT: Receipt signature mismatch for {bill['bill_number']}. Potential financial record tampering!"


    def get_tax_rate(self) -> float:
        """Get the current operational tax/GST rate."""
        return self.db.get_tax_rate()

    def update_tax_rate(self, admin_session: UserSession, new_rate: float) -> Tuple[bool, str]:
        """Allow an Administrator to customize the operational tax/GST rate (Poka-Yoke bounded 0% to 50%)."""
        if not admin_session or not admin_session.is_admin():
            return False, "Access Denied: Only Administrators can configure system tax rates."

        try:
            rate_float = float(new_rate)
        except (ValueError, TypeError):
            return False, "Poka-Yoke Rejection: Invalid numeric tax rate."

        if rate_float < 0.0 or rate_float > 0.50:
            return False, "Poka-Yoke Rejection: Tax rate must be between 0.0 (0%) and 0.50 (50%)."

        self.db.set_setting("tax_rate", str(rate_float))
        return True, f"Tax rate updated successfully to {rate_float * 100:.1f}%."


# Default singleton instance
billing_service = BillingService()
