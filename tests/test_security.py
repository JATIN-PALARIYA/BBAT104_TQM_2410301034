"""Unit Tests for Cryptographic Security & Poka-Yoke Validation Core
Restaurant Billing System [Q04: Improve Security] - BBAT104
Student: Jatin Palariya (Roll No: 2410301034)
"""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.security import (
    decrypt_customer_phone,
    encrypt_customer_phone,
    generate_receipt_checksum,
    hash_password,
    hash_recovery_key,
    sanitize_string,
    validate_customer_phone,
    validate_discount_percent,
    validate_password_strength,
    validate_price,
    validate_quantity,
    verify_password,
    verify_receipt_checksum,
    verify_recovery_key,
)


class TestSecurityCore(unittest.TestCase):
    """Test suite covering PBKDF2 password hashing, AES encryption, receipt checksum, and Poka-Yoke validation."""

    def test_pbkdf2_password_hashing_and_verification(self):
        """Verify PBKDF2-HMAC-SHA256 hashing and timing-safe verification."""
        password = "AdminSecret@2026"
        hashed, salt = hash_password(password)

        self.assertNotEqual(password, hashed, "Plaintext password must not equal hash")
        self.assertEqual(len(hashed), 64, "SHA-256 digest hex must be 64 characters")
        self.assertEqual(len(salt), 32, "Salt hex must be 32 characters (16 bytes)")

        # Correct password must verify
        self.assertTrue(verify_password(password, hashed, salt))

        # Incorrect password must fail
        self.assertFalse(verify_password("WrongPassword@123", hashed, salt))
        self.assertFalse(verify_password("", hashed, salt))

    def test_pbkdf2_salt_uniqueness(self):
        """Verify that hashing the same password twice yields distinct salts and hashes."""
        pw = "TestPassword#123"
        hash1, salt1 = hash_password(pw)
        hash2, salt2 = hash_password(pw)

        self.assertNotEqual(salt1, salt2, "Salts must be randomly generated and unique")
        self.assertNotEqual(hash1, hash2, "Hashes of the same password must differ due to unique salts")

    def test_recovery_key_hashing(self):
        """Verify Master Recovery Key hashing and verification."""
        recovery_key = "RECOVERY-KEY-AMRAPALI-2026"
        hashed, salt = hash_recovery_key(recovery_key)

        self.assertTrue(verify_recovery_key(recovery_key, hashed, salt))
        self.assertFalse(verify_recovery_key("INVALID-KEY", hashed, salt))

    def test_aes_fernet_phone_encryption_and_decryption(self):
        """Verify symmetric AES-Fernet encryption of customer phone numbers."""
        phone = "9876543210"
        encrypted = encrypt_customer_phone(phone)

        self.assertIsNotNone(encrypted)
        self.assertNotEqual(phone, encrypted)

        # Decryption returns original plaintext
        decrypted = decrypt_customer_phone(encrypted)
        self.assertEqual(decrypted, phone)

        # Empty/None input handling
        self.assertIsNone(encrypt_customer_phone(None))
        self.assertIsNone(encrypt_customer_phone(""))
        self.assertIsNone(decrypt_customer_phone(None))

        # Tampered ciphertext handling
        corrupted = encrypted[:-4] + "AAAA"
        self.assertEqual(decrypt_customer_phone(corrupted), "[Decryption Error]")

    def test_receipt_hmac_checksum(self):
        """Verify receipt HMAC-SHA256 tamper-evident checksums."""
        bill_num = "BILL-20261011-0001"
        created_at = "2026-10-11 20:30:00"
        total = 525.00

        checksum = generate_receipt_checksum(bill_num, created_at, total)
        self.assertEqual(len(checksum), 64)

        # Valid checksum verifies
        self.assertTrue(verify_receipt_checksum(bill_num, created_at, total, checksum))

        # Tampered total fails verification
        self.assertFalse(verify_receipt_checksum(bill_num, created_at, 500.00, checksum))

        # Tampered bill number fails verification
        self.assertFalse(verify_receipt_checksum("BILL-20261011-0002", created_at, total, checksum))

    def test_poka_yoke_password_policy(self):
        """Verify password complexity requirements enforcement."""
        # Valid password
        valid, msg = validate_password_strength("Secure@1234")
        self.assertTrue(valid, msg)

        # Short password (< 8 chars)
        valid, msg = validate_password_strength("Sec@1")
        self.assertFalse(valid)
        self.assertIn("at least 8 characters", msg)

        # Missing uppercase
        valid, _ = validate_password_strength("secure@1234")
        self.assertFalse(valid)

        # Missing digit
        valid, _ = validate_password_strength("Secure@abcd")
        self.assertFalse(valid)

        # Missing special symbol
        valid, _ = validate_password_strength("Secure12345")
        self.assertFalse(valid)

    def test_poka_yoke_quantity_validation(self):
        """Verify integer quantity boundary enforcement."""
        # Valid quantities
        valid, val, _ = validate_quantity(1)
        self.assertTrue(valid)
        self.assertEqual(val, 1)

        valid, val, _ = validate_quantity("5")
        self.assertTrue(valid)
        self.assertEqual(val, 5)

        # Rejection of zero and negative quantities
        valid, _, _ = validate_quantity(0)
        self.assertFalse(valid)

        valid, _, _ = validate_quantity(-3)
        self.assertFalse(valid)

        # Rejection of excessive quantities
        valid, _, _ = validate_quantity(1000)
        self.assertFalse(valid)

        # Rejection of non-numeric text
        valid, _, _ = validate_quantity("abc")
        self.assertFalse(valid)

    def test_poka_yoke_price_validation(self):
        """Verify unit price positive boundary enforcement."""
        # Valid prices
        valid, val, _ = validate_price("150.50")
        self.assertTrue(valid)
        self.assertEqual(val, 150.50)

        # Rejection of zero and negative prices
        valid, _, _ = validate_price(0.0)
        self.assertFalse(valid)

        valid, _, _ = validate_price("-50.0")
        self.assertFalse(valid)

        # Non-numeric
        valid, _, _ = validate_price("free")
        self.assertFalse(valid)

    def test_poka_yoke_discount_bounds(self):
        """Verify discount percentage boundary (0% to 20%)."""
        # Valid discounts
        valid, val, _ = validate_discount_percent(0.0)
        self.assertTrue(valid)
        self.assertEqual(val, 0.0)

        valid, val, _ = validate_discount_percent("10")
        self.assertTrue(valid)
        self.assertEqual(val, 10.0)

        valid, val, _ = validate_discount_percent(20.0)
        self.assertTrue(valid)
        self.assertEqual(val, 20.0)

        # Exceeds maximum 20% limit
        valid, _, msg = validate_discount_percent(25.0)
        self.assertFalse(valid)
        self.assertIn("cannot exceed", msg)

        # Negative discount
        valid, _, _ = validate_discount_percent(-5.0)
        self.assertFalse(valid)

    def test_customer_phone_validation(self):
        """Verify 10-digit mobile number validation."""
        # Valid
        valid, clean, _ = validate_customer_phone("9876543210")
        self.assertTrue(valid)
        self.assertEqual(clean, "9876543210")

        # Optional empty
        valid, clean, _ = validate_customer_phone("")
        self.assertTrue(valid)
        self.assertIsNone(clean)

        # Invalid (less than 10 digits or invalid starting digit)
        valid, _, _ = validate_customer_phone("12345")
        self.assertFalse(valid)

        valid, _, _ = validate_customer_phone("1234567890")  # starts with 1
        self.assertFalse(valid)

    def test_string_sanitization(self):
        """Verify string trimming and control character removal."""
        raw = "  \x00\x1fPaneer Tikka \t "
        sanitized = sanitize_string(raw, max_len=20)
        self.assertEqual(sanitized, "Paneer Tikka")


if __name__ == "__main__":
    unittest.main()
