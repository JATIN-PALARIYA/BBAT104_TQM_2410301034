"""Poka-Yoke Defensive Input Validation & Sanitization [Q04: Security Core]
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
"""

import re
from typing import Any, Optional, Tuple


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Enforce password complexity policy:
    - Minimum 8 characters
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one numeric digit (0-9)
    - At least one special symbol (!@#$%^&*()-_=+[]{}|;:,.<>?)
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter (a-z)."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one numeric digit (0-9)."
    if not re.search(r"[!@#$%^&*()\-_=+\[\]{}|;:,.<>?]", password):
        return False, "Password must contain at least one special symbol (!@#$%^&*...)."
    return True, "Password meets all complexity requirements."


def validate_quantity(qty_input: Any) -> Tuple[bool, int, str]:
    """Poka-Yoke positive integer quantity guard: 1 <= qty <= 999."""
    try:
        qty = int(qty_input)
        if qty <= 0:
            return False, 0, "Quantity must be a positive integer greater than zero."
        if qty > 999:
            return False, 0, "Quantity cannot exceed 999 items per line."
        return True, qty, "Valid quantity."
    except (ValueError, TypeError):
        return False, 0, "Quantity must be a valid whole number."


def validate_price(price_input: Any) -> Tuple[bool, float, str]:
    """Poka-Yoke positive unit price guard: 0.01 <= price <= 99999.00."""
    try:
        price = float(price_input)
        if price <= 0.0:
            return False, 0.0, "Unit price must be strictly greater than ₹0.00."
        if price > 99_999.0:
            return False, 0.0, "Unit price cannot exceed ₹99,999.00."
        return True, round(price, 2), "Valid unit price."
    except (ValueError, TypeError):
        return False, 0.0, "Price must be a valid numeric amount."


def validate_discount_percent(discount_input: Any) -> Tuple[bool, float, str]:
    """Poka-Yoke discount boundary guard: 0.0% <= discount <= 20.0%."""
    try:
        if discount_input is None or str(discount_input).strip() == "":
            return True, 0.0, "No discount applied."
        discount = float(discount_input)
        if discount < 0.0:
            return False, 0.0, "Discount percentage cannot be negative."
        if discount > 20.0:
            return False, 0.0, "Discount cannot exceed the authorized limit of 20.0%."
        return True, round(discount, 2), "Valid discount rate."
    except (ValueError, TypeError):
        return False, 0.0, "Discount must be a valid numeric percentage."


def validate_customer_phone(phone_input: Any) -> Tuple[bool, Optional[str], str]:
    """Validate optional 10-digit customer mobile number."""
    if phone_input is None or str(phone_input).strip() == "":
        return True, None, "No phone number provided."
    clean = re.sub(r"[\s\-\(\)]", "", str(phone_input).strip())
    if re.fullmatch(r"[6-9]\d{9}", clean):
        return True, clean, "Valid 10-digit mobile number."
    return False, None, "Customer phone must be a valid 10-digit mobile number (starting with 6-9)."


def sanitize_string(text: Any, max_len: int = 100) -> str:
    """Strip whitespace, control characters, and constrain string length."""
    if text is None:
        return ""
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", str(text)).strip()
    return cleaned[:max_len]
