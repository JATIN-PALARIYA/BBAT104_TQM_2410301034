"""Database Engine & SQLite Connection Manager [Review 2: Persistence Layer]
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Base Project Paths (src/database/manager.py -> src/database -> src -> Project Root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "config" / "default_settings.json"
SCHEMA_PATH = BASE_DIR / "schema" / "schema.sql"
SEED_PATH = BASE_DIR / "schema" / "seed.sql"
DEFAULT_DB_PATH = BASE_DIR / "db" / "restaurant_pos.db"


DEFAULT_RESTAURANT_NAME = "Amrapali Campus Diner"
DEFAULT_TAX_RATE = 0.05


def load_config() -> Dict[str, Any]:
    """Load default application configuration settings."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "restaurant_name": DEFAULT_RESTAURANT_NAME,
        "tax_rate": DEFAULT_TAX_RATE,
        "currency_symbol": "₹",
        "max_failed_attempts": 5,
        "lockout_duration_seconds": 60,
        "password_min_length": 8,
        "max_discount_percent": 20.0,
        "db_path": "db/restaurant_pos.db",
    }


class DatabaseManager:
    """Manages SQLite connections, schema initialization, and transactional queries."""

    def __init__(self, db_path: Optional[Path | str] = None):
        if db_path is None:
            config = load_config()
            configured_path = config.get("db_path", "db/restaurant_pos.db")
            self.db_path = BASE_DIR / configured_path
        else:
            self.db_path = Path(db_path)

        # Ensure directory exists for persistent file-based databases
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection with foreign keys and WAL mode."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=10.0,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        if str(self.db_path) != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    @contextmanager
    def transaction(self):
        """Context manager providing an atomic database transaction with automatic commit/rollback."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_schema(self, schema_file: Optional[Path] = None, seed_file: Optional[Path] = None):
        """Run DDL schema script and baseline seeds if tables do not exist."""
        schema_path = schema_file or SCHEMA_PATH
        seed_path = seed_file or SEED_PATH

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found at: {schema_path}")

        # Check if menu_items needs legacy migration outside active transaction
        raw_conn = sqlite3.connect(str(self.db_path))
        try:
            raw_conn.execute("PRAGMA foreign_keys = OFF;")
            table_sql_row = raw_conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='menu_items';"
            ).fetchone()
            if table_sql_row and table_sql_row[0] and "CHECK(category IN" in table_sql_row[0]:
                raw_conn.execute("BEGIN IMMEDIATE;")
                raw_conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS menu_items_migrated (
                        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_name TEXT UNIQUE NOT NULL,
                        category TEXT NOT NULL,
                        price REAL NOT NULL CHECK(price > 0.0),
                        is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
                        created_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime')),
                        updated_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime'))
                    );
                    """
                )
                raw_conn.execute("INSERT INTO menu_items_migrated SELECT * FROM menu_items;")
                raw_conn.execute("DROP TABLE menu_items;")
                raw_conn.execute("ALTER TABLE menu_items_migrated RENAME TO menu_items;")
                raw_conn.execute("CREATE INDEX IF NOT EXISTS idx_menu_category ON menu_items(category);")
                raw_conn.execute("CREATE INDEX IF NOT EXISTS idx_menu_active ON menu_items(is_active);")
                raw_conn.execute("COMMIT;")

            # Check if audit_logs has legacy hardcoded CHECK constraint on action_type
            audit_sql_row = raw_conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='audit_logs';"
            ).fetchone()
            if audit_sql_row and audit_sql_row[0] and "CHECK(action_type IN" in audit_sql_row[0]:
                raw_conn.execute("BEGIN IMMEDIATE;")
                raw_conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_logs_migrated (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime')),
                        user_id INTEGER,
                        username TEXT NOT NULL,
                        action_type TEXT NOT NULL,
                        details TEXT NOT NULL,
                        prev_hash TEXT NOT NULL,
                        record_hash TEXT NOT NULL
                    );
                    """
                )
                raw_conn.execute("INSERT INTO audit_logs_migrated SELECT * FROM audit_logs;")
                raw_conn.execute("DROP TABLE audit_logs;")
                raw_conn.execute("ALTER TABLE audit_logs_migrated RENAME TO audit_logs;")
                raw_conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);")
                raw_conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action_type);")
                raw_conn.execute("COMMIT;")
        finally:
            raw_conn.close()

        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        with self.transaction() as conn:
            conn.executescript(schema_sql)

            # Check if menu_items already has data; if empty, run seed script
            cursor = conn.execute("SELECT COUNT(*) AS cnt FROM menu_items;")
            row = cursor.fetchone()
            if row and row["cnt"] == 0 and seed_path.exists():
                with open(seed_path, "r", encoding="utf-8") as sf:
                    seed_sql = sf.read()
                conn.executescript(seed_sql)

            # Ensure menu_categories table exists and has baseline categories
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS menu_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_name TEXT UNIQUE NOT NULL,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime'))
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_category_name ON menu_categories(category_name);")

            # Seed default categories if empty
            cat_count_cur = conn.execute("SELECT COUNT(*) FROM menu_categories;")
            cat_cnt_row = cat_count_cur.fetchone()
            if cat_cnt_row and cat_cnt_row[0] == 0:
                defaults = ["Beverages", "Starters", "Main Course", "Desserts", "Breads & Rice"]
                for idx, c_name in enumerate(defaults, start=1):
                    conn.execute(
                        "INSERT OR IGNORE INTO menu_categories (category_id, category_name, display_order) VALUES (?, ?, ?);",
                        (idx, c_name, idx),
                    )

            # Populate any existing menu_items categories not yet in menu_categories
            conn.execute(
                """
                INSERT OR IGNORE INTO menu_categories (category_name)
                SELECT DISTINCT category FROM menu_items WHERE category IS NOT NULL AND category != '';
                """
            )

    def execute(self, query: str, params: Tuple[Any, ...] = ()) -> int:
        """Execute a single parameterized write query and return the last row id."""
        with self.transaction() as conn:
            cursor = conn.execute(query, params)
            return cursor.lastrowid

    def execute_many(self, query: str, seq_of_params: List[Tuple[Any, ...]]) -> int:
        """Execute a batch of parameterized write queries."""
        with self.transaction() as conn:
            cursor = conn.executemany(query, seq_of_params)
            return cursor.rowcount

    def fetch_one(self, query: str, params: Tuple[Any, ...] = ()) -> Optional[sqlite3.Row]:
        """Execute a parameterized query and return the first matching row."""
        conn = self.get_connection()
        try:
            cursor = conn.execute(query, params)
            return cursor.fetchone()
        finally:
            conn.close()

    def fetch_all(self, query: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
        """Execute a parameterized query and return all matching rows."""
        conn = self.get_connection()
        try:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
        finally:
            conn.close()

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieve a system setting value by key."""
        row = self.fetch_one("SELECT setting_value FROM app_settings WHERE setting_key = ?;", (key,))
        if row:
            return row["setting_value"]
        return default

    def get_restaurant_name(self) -> str:
        """Retrieve the configured restaurant name, falling back to canonical default."""
        return str(self.get_setting("restaurant_name", DEFAULT_RESTAURANT_NAME))

    def get_tax_rate(self) -> float:
        """Retrieve the configured tax rate as a float, falling back to canonical default."""
        val = self.get_setting("tax_rate", DEFAULT_TAX_RATE)
        try:
            return float(val)
        except (ValueError, TypeError):
            return DEFAULT_TAX_RATE

    def set_setting(self, key: str, value: str):
        """Update or insert a system setting value."""
        self.execute(
            """
            INSERT INTO app_settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, DATETIME('now', 'localtime'))
            ON CONFLICT(setting_key) DO UPDATE SET
                setting_value = excluded.setting_value,
                updated_at = excluded.updated_at;
            """,
            (key, str(value)),
        )


# Default singleton instance for application use
db = DatabaseManager()
