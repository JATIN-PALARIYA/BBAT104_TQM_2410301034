"""Tamper-Evident SHA-256 Hash-Chained Audit Trail Logger [Q04: Security Core]
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
"""

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.database import db

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

VALID_ACTION_TYPES = {
    "USER_LOGIN_SUCCESS",
    "USER_LOGIN_FAILED",
    "USER_LOGOUT",
    "ACCOUNT_LOCKED",
    "PASSWORD_RESET",
    "MENU_ITEM_ADDED",
    "MENU_ITEM_UPDATED",
    "MENU_ITEM_DEACTIVATED",
    "CATEGORY_ADDED",
    "CATEGORY_RENAMED",
    "CATEGORY_DELETED",
    "BILL_GENERATED",
    "BILL_VOIDED",
    "INTEGRITY_CHECK_RUN",
}


def calculate_record_hash(
    log_id: int,
    timestamp: str,
    username: str,
    action_type: str,
    details: str,
    prev_hash: str,
) -> str:
    """Calculate the cryptographic SHA-256 hash digest for an audit record."""
    payload = f"{log_id}|{timestamp}|{username}|{action_type}|{details}|{prev_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditLogger:
    """Provides tamper-evident event logging with unbroken SHA-256 cryptographic hash-chaining."""

    def __init__(self, db_manager=None):
        self.db = db_manager or db

    def log_event(
        self,
        action_type: str,
        username: str,
        details: str,
        user_id: Optional[int] = None,
        custom_time: Optional[str] = None,
        conn: Optional[Any] = None,
    ) -> int:
        """Append an event to the audit trail, maintaining cryptographic hash-chaining."""
        if action_type not in VALID_ACTION_TYPES:
            raise ValueError(f"Invalid audit action type: {action_type}")

        timestamp = custom_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def _execute_with_conn(c):
            cursor = c.execute("SELECT log_id, record_hash FROM audit_logs ORDER BY log_id DESC LIMIT 1;")
            last_record = cursor.fetchone()

            if last_record:
                prev_hash = last_record["record_hash"]
                next_id = last_record["log_id"] + 1
            else:
                prev_hash = GENESIS_HASH
                next_id = 1

            record_hash = calculate_record_hash(
                log_id=next_id,
                timestamp=timestamp,
                username=username,
                action_type=action_type,
                details=details,
                prev_hash=prev_hash,
            )

            ins_cursor = c.execute(
                """
                INSERT INTO audit_logs (log_id, timestamp, user_id, username, action_type, details, prev_hash, record_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (next_id, timestamp, user_id, username, action_type, details, prev_hash, record_hash),
            )
            return ins_cursor.lastrowid

        if conn is not None:
            return _execute_with_conn(conn)
        else:
            with self.db.transaction() as transaction_conn:
                return _execute_with_conn(transaction_conn)

    def get_logs(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve historical audit records in reverse chronological order."""
        rows = self.db.fetch_all(
            """
            SELECT log_id, timestamp, user_id, username, action_type, details, prev_hash, record_hash
            FROM audit_logs
            ORDER BY log_id DESC
            LIMIT ? OFFSET ?;
            """,
            (limit, offset),
        )
        return [dict(r) for r in rows]

    def get_total_logs_count(self) -> int:
        """Count total audit log entries in the database for efficient pagination."""
        row = self.db.fetch_one("SELECT COUNT(*) FROM audit_logs;")
        if row is not None:
            return int(row[0])
        return 0

    def verify_audit_integrity(self) -> Dict[str, Any]:
        """Walk the entire cryptographic hash chain from genesis to head.
        
        Detects:
        - Any modified record content (record_hash mismatch)
        - Any deleted rows (prev_hash mismatch or sequence gap)
        - Any inserted unauthorized rows
        """
        rows = self.db.fetch_all(
            """
            SELECT log_id, timestamp, user_id, username, action_type, details, prev_hash, record_hash
            FROM audit_logs
            ORDER BY log_id ASC;
            """
        )

        total_records = len(rows)
        if total_records == 0:
            return {
                "is_valid": True,
                "total_records": 0,
                "corrupted_records": [],
                "details": "Audit trail is empty. Hash chain is clean.",
            }

        expected_prev_hash = GENESIS_HASH
        corrupted_ids = []
        error_reasons = []

        for expected_id, row in enumerate(rows, start=1):
            curr_id = row["log_id"]
            curr_timestamp = row["timestamp"]
            curr_user = row["username"]
            curr_action = row["action_type"]
            curr_details = row["details"]
            curr_prev_hash = row["prev_hash"]
            curr_record_hash = row["record_hash"]

            # 1. Check sequence integrity
            if curr_id != expected_id:
                corrupted_ids.append(curr_id)
                error_reasons.append(f"Sequence break: Expected log_id {expected_id}, found {curr_id}.")

            # 2. Check previous hash link
            if curr_prev_hash != expected_prev_hash:
                corrupted_ids.append(curr_id)
                error_reasons.append(f"Broken chain link at log_id {curr_id}: prev_hash does not match prior record_hash.")

            # 3. Recompute and verify record hash
            recomputed = calculate_record_hash(
                log_id=curr_id,
                timestamp=curr_timestamp,
                username=curr_user,
                action_type=curr_action,
                details=curr_details,
                prev_hash=curr_prev_hash,
            )

            if recomputed != curr_record_hash:
                corrupted_ids.append(curr_id)
                error_reasons.append(f"Data tampering detected at log_id {curr_id}: Hash mismatch.")

            expected_prev_hash = curr_record_hash

        is_valid = len(corrupted_ids) == 0
        details = (
            f"All {total_records} records verified successfully. Cryptographic hash chain is intact."
            if is_valid
            else f"Integrity check failed: {'; '.join(error_reasons)}"
        )

        return {
            "is_valid": is_valid,
            "total_records": total_records,
            "corrupted_records": sorted(list(set(corrupted_ids))),
            "details": details,
        }


# Default singleton instance
audit_logger = AuditLogger()
