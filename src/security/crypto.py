"""Cryptographic Primitives & Digital Signatures [Q04: Security Core]
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
"""

import hashlib
import hmac
import os
import secrets
from pathlib import Path
from typing import Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
KEY_FILE_PATH = CONFIG_DIR / ".encryption_key"

# PBKDF2 parameters
PBKDF2_ITERATIONS = 100_000
SALT_BYTES = 16


def get_or_create_encryption_key() -> bytes:
    """Retrieve or generate the symmetric 256-bit AES-Fernet encryption key."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if KEY_FILE_PATH.exists():
        with open(KEY_FILE_PATH, "rb") as f:
            key = f.read().strip()
            if key:
                return key

    # Generate new Fernet key and save securely
    new_key = Fernet.generate_key()
    with open(KEY_FILE_PATH, "wb") as f:
        f.write(new_key)
    return new_key


_FERNET_INSTANCE: Optional[Fernet] = None


def get_fernet() -> Fernet:
    """Singleton getter for the AES-Fernet cipher instance."""
    global _FERNET_INSTANCE
    if _FERNET_INSTANCE is None:
        key = get_or_create_encryption_key()
        _FERNET_INSTANCE = Fernet(key)
    return _FERNET_INSTANCE


# ----------------------------------------------------------------------
# 1. Password & Recovery Key Hashing (PBKDF2-HMAC-SHA256)
# ----------------------------------------------------------------------

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Derive salted PBKDF2-HMAC-SHA256 password hash.
    
    Returns:
        (hash_hex: str, salt_hex: str)
    """
    if salt is None:
        salt = secrets.token_hex(SALT_BYTES)

    salt_bytes = salt.encode("utf-8")
    pw_bytes = password.encode("utf-8")
    derived_hash = hashlib.pbkdf2_hmac("sha256", pw_bytes, salt_bytes, PBKDF2_ITERATIONS)
    return derived_hash.hex(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Timing-safe verification of a password against a stored PBKDF2 hash and salt."""
    if not password or not stored_hash or not salt:
        return False
    computed_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(computed_hash, stored_hash)


def hash_recovery_key(recovery_key: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Derive salted PBKDF2 hash for the Admin Master Recovery Key."""
    return hash_password(recovery_key, salt)


def verify_recovery_key(recovery_key: str, stored_hash: str, salt: str) -> bool:
    """Timing-safe verification of the Admin Master Recovery Key."""
    return verify_password(recovery_key, stored_hash, salt)


# ----------------------------------------------------------------------
# 2. Symmetric AES-Fernet Encryption for Customer Data at Rest
# ----------------------------------------------------------------------

def encrypt_customer_phone(phone: Optional[str]) -> Optional[str]:
    """Encrypt customer phone number using AES-Fernet at rest.
    
    Returns:
        Base64 encoded ciphertext string, or None if phone is empty.
    """
    if not phone or not phone.strip():
        return None
    fernet = get_fernet()
    encrypted_bytes = fernet.encrypt(phone.strip().encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_customer_phone(encrypted_phone: Optional[str]) -> Optional[str]:
    """Decrypt customer phone number from AES-Fernet ciphertext.
    
    Returns:
        Plaintext phone string, or None if decryption fails or input is empty.
    """
    if not encrypted_phone or not encrypted_phone.strip():
        return None
    try:
        fernet = get_fernet()
        decrypted_bytes = fernet.decrypt(encrypted_phone.strip().encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except (InvalidToken, Exception):
        return "[Decryption Error]"


# ----------------------------------------------------------------------
# 3. Receipt Verification Digital Checksum (HMAC-SHA256)
# ----------------------------------------------------------------------

def generate_receipt_checksum(bill_number: str, created_at: str, final_total: float) -> str:
    """Generate an HMAC-SHA256 digital signature over bill metadata."""
    key = get_or_create_encryption_key()
    total_str = f"{final_total:.2f}"
    message = f"{bill_number}|{created_at}|{total_str}".encode("utf-8")
    signature = hmac.new(key, message, hashlib.sha256).hexdigest()
    return signature


def verify_receipt_checksum(bill_number: str, created_at: str, final_total: float, stored_checksum: str) -> bool:
    """Verify that a receipt's bill number, date, and grand total have not been tampered with."""
    expected = generate_receipt_checksum(bill_number, created_at, final_total)
    return hmac.compare_digest(expected, stored_checksum)
