"""Monospace Receipt Invoice Formatter [Q04: Security & Billing]
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
"""

from typing import Any, Dict, List, Optional


def generate_receipt_text(
    store_name: str,
    bill_number: str,
    created_at: str,
    cashier_name: str,
    items: List[Dict[str, Any]],
    totals: Dict[str, float],
    payment_mode: str,
    customer_phone: Optional[str],
    receipt_hash: str,
) -> str:
    """Format an itemized, monospace receipt invoice with cryptographic checksum."""
    sep = "=" * 42
    thin_sep = "-" * 42

    phone_display = (
        f"Customer: +91 {customer_phone[:3]}***{customer_phone[-4:]}"
        if customer_phone
        else "Customer: Counter Walk-in"
    )

    lines = [
        sep,
        f"{store_name.center(42)}",
        "AITS Campus, Haldwani (Uttarakhand)".center(42),
        "GSTIN: 05AABCA1234D1Z5".center(42),
        sep,
        f"Bill No : {bill_number:<20}",
        f"Date    : {created_at:<20}",
        f"Cashier : {cashier_name:<20}",
        f"{phone_display:<20}",
        f"Payment : {payment_mode:<20}",
        thin_sep,
        f"{'Item':<20} {'Qty':>4} {'Rate':>7} {'Amount':>8}",
        thin_sep,
    ]

    for item in items:
        name = item["name"][:19]
        lines.append(
            f"{name:<20} {item['qty']:>4} {item['rate']:>7.2f} {item['total']:>8.2f}"
        )

    lines.extend([
        thin_sep,
        f"{'Subtotal:':<28} ₹{totals['subtotal']:>11.2f}",
    ])

    if totals.get("discount_amount", 0.0) > 0.0:
        disc_pct = totals.get("discount_percent", 0.0)
        disc_label = f"Discount ({disc_pct:.0f}%):"
        disc_val = f"-₹{totals['discount_amount']:.2f}"
        lines.append(f"{disc_label:<28} {disc_val:>12}")
        taxable_val = f"₹{totals.get('taxable_amount', totals['subtotal']):.2f}"
        lines.append(f"{'Taxable Amount:':<28} {taxable_val:>12}")

    gst_pct = int(totals.get("tax_rate", 0.05) * 100)
    gst_label = f"Incl. GST ({gst_pct}%):"
    gst_val = f"₹{totals['tax_amount']:.2f}"
    lines.append(f"{gst_label:<28} {gst_val:>12}")
    lines.extend([
        sep,
        f"{'GRAND TOTAL:':<28} ₹{totals['final_total']:>11.2f}",
        sep,
        "Digital Checksum (HMAC-SHA256):",
        f"{receipt_hash[:40]}...",
        thin_sep,
        "Prices are inclusive of GST".center(42),
        "Thank You for Dining With Us!".center(42),
        "Please Visit Again".center(42),
        sep,
    ])

    return "\n".join(lines)
