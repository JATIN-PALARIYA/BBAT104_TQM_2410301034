-- =============================================================================
-- Restaurant Billing System with Enhanced Security Architecture [Q04]
-- Relational Database Schema DDL (SQLite 3.35+)
-- Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
-- =============================================================================

PRAGMA foreign_keys = ON;

-- 1. users Table: Role-based credentials, recovery key hash, and lockout state
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,         -- 64-character hex string (PBKDF2-HMAC-SHA256)
    salt TEXT NOT NULL,                  -- 32-character hex string (16 bytes random salt)
    role TEXT NOT NULL CHECK(role IN ('Admin', 'Cashier')),
    recovery_key_hash TEXT DEFAULT NULL, -- Salted hash of Admin Master Recovery Key
    must_change_password INTEGER NOT NULL DEFAULT 0 CHECK(must_change_password IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Inactive', 'Locked')),
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT DEFAULT NULL,       -- ISO-8601 timestamp string or NULL
    created_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- 2a. menu_categories Table: Food catalog categories
CREATE TABLE IF NOT EXISTS menu_categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT UNIQUE NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_category_name ON menu_categories(category_name);

-- 2b. menu_items Table: Food catalog with soft-deactivation
CREATE TABLE IF NOT EXISTS menu_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL CHECK(price > 0.0), -- Poka-Yoke non-negative constraint
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_menu_category ON menu_items(category);
CREATE INDEX IF NOT EXISTS idx_menu_active ON menu_items(is_active);

-- 3. bills Table: Invoice transaction headers with encrypted phone & HMAC checksum
CREATE TABLE IF NOT EXISTS bills (
    bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_number TEXT UNIQUE NOT NULL,    -- E.g., 'BILL-YYYYMMDD-XXXX'
    cashier_id INTEGER NOT NULL,
    customer_phone_enc TEXT DEFAULT NULL, -- AES/Fernet ciphertext string
    subtotal REAL NOT NULL CHECK(subtotal >= 0.0),
    tax_rate REAL NOT NULL DEFAULT 0.05 CHECK(tax_rate >= 0.0), -- 5% GST assumption
    tax_amount REAL NOT NULL CHECK(tax_amount >= 0.0),
    discount_amount REAL NOT NULL DEFAULT 0.0 CHECK(discount_amount >= 0.0),
    final_total REAL NOT NULL CHECK(final_total >= 0.0),
    payment_mode TEXT NOT NULL DEFAULT 'Cash' CHECK(payment_mode IN ('Cash', 'Card', 'UPI')),
    status TEXT NOT NULL DEFAULT 'COMPLETED' CHECK(status IN ('COMPLETED', 'VOID')),
    void_reason TEXT DEFAULT NULL,
    receipt_hash TEXT NOT NULL,          -- HMAC-SHA256 signature for receipt verification
    created_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime')),
    FOREIGN KEY (cashier_id) REFERENCES users(user_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_bills_number ON bills(bill_number);
CREATE INDEX IF NOT EXISTS idx_bills_cashier ON bills(cashier_id);
CREATE INDEX IF NOT EXISTS idx_bills_date ON bills(created_at);

-- 4. bill_items Table: Line items snapshotting historical item names and unit prices
CREATE TABLE IF NOT EXISTS bill_items (
    item_line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL,
    menu_item_id INTEGER NOT NULL,
    item_name_snapshot TEXT NOT NULL,
    unit_price_snapshot REAL NOT NULL CHECK(unit_price_snapshot > 0.0),
    quantity INTEGER NOT NULL CHECK(quantity > 0), -- Poka-Yoke positive quantity guard
    line_total REAL NOT NULL CHECK(line_total > 0.0),
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE,
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(item_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_bill_items_bill ON bill_items(bill_id);

-- 5. audit_logs Table: Tamper-evident append-only event log with SHA-256 hash chaining
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime')),
    user_id INTEGER,                     -- NULL allowed for failed logins by unknown users
    username TEXT NOT NULL,
    action_type TEXT NOT NULL,
    details TEXT NOT NULL,
    prev_hash TEXT NOT NULL,             -- SHA-256 hex of preceding log record (GENESIS_HASH for log 1)
    record_hash TEXT NOT NULL            -- SHA-256 hex of (log_id || timestamp || username || action_type || details || prev_hash)
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);

-- 6. app_settings Table: Configurable operational parameters
CREATE TABLE IF NOT EXISTS app_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime'))
);
