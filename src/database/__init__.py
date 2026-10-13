"""Database Persistence Package [Review 2: SQLite Layer]
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
"""

from src.database.manager import (
    BASE_DIR,
    CONFIG_PATH,
    DEFAULT_DB_PATH,
    SCHEMA_PATH,
    SEED_PATH,
    DatabaseManager,
    db,
    load_config,
)

__all__ = [
    "BASE_DIR",
    "CONFIG_PATH",
    "SCHEMA_PATH",
    "SEED_PATH",
    "DEFAULT_DB_PATH",
    "DatabaseManager",
    "db",
    "load_config",
]
