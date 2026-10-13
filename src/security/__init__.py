"""Security & Poka-Yoke Validation Package [Q04: Improve Security]
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
"""

from src.security.crypto import (
    PBKDF2_ITERATIONS,
    SALT_BYTES,
    decrypt_customer_phone,
    encrypt_customer_phone,
    generate_receipt_checksum,
    get_fernet,
    get_or_create_encryption_key,
    hash_password,
    hash_recovery_key,
    verify_password,
    verify_receipt_checksum,
    verify_recovery_key,
)
from src.security.validators import (
    sanitize_string,
    validate_customer_phone,
    validate_discount_percent,
    validate_password_strength,
    validate_price,
    validate_quantity,
)

__all__ = [
    # Cryptographic APIs
    "PBKDF2_ITERATIONS",
    "SALT_BYTES",
    "get_or_create_encryption_key",
    "get_fernet",
    "hash_password",
    "verify_password",
    "hash_recovery_key",
    "verify_recovery_key",
    "encrypt_customer_phone",
    "decrypt_customer_phone",
    "generate_receipt_checksum",
    "verify_receipt_checksum",
    # Validation APIs
    "validate_password_strength",
    "validate_quantity",
    "validate_price",
    "validate_discount_percent",
    "validate_customer_phone",
    "sanitize_string",
]
