"""Authentication, Lockout Protection & Password Reset Service [Q04: Security Core]
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple

from src.audit import audit_logger
from src.auth.session import UserSession
from src.database import db
from src.security import (
    hash_password,
    hash_recovery_key,
    sanitize_string,
    validate_password_strength,
    verify_password,
    verify_recovery_key,
)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 60


class AuthService:
    """Manages user authentication, lockout guard, RBAC, and secure password recovery."""

    def __init__(self, db_manager=None, audit_engine=None):
        self.db = db_manager or db
        self.audit = audit_engine or audit_logger
        self.active_session: Optional[UserSession] = None

    def is_setup_needed(self) -> bool:
        """Check if any users exist in the database."""
        row = self.db.fetch_one("SELECT COUNT(*) AS cnt FROM users;")
        return row is None or row["cnt"] == 0

    def initial_setup_admin(
        self, username: str, password: str, master_recovery_key: str
    ) -> Tuple[bool, str]:
        """First-Time Setup Wizard: create initial Administrator and Master Recovery Key."""
        if not self.is_setup_needed():
            return False, "Initial setup has already been completed."

        username = sanitize_string(username, 30)
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters."

        pw_valid, pw_msg = validate_password_strength(password)
        if not pw_valid:
            return False, pw_msg

        rec_valid, rec_msg = validate_password_strength(master_recovery_key)
        if not rec_valid:
            return False, f"Master Recovery Key must be strong: {rec_msg}"

        pw_hash, pw_salt = hash_password(password)
        rec_hash, _ = hash_recovery_key(master_recovery_key, pw_salt)

        user_id = self.db.execute(
            """
            INSERT INTO users (username, password_hash, salt, role, recovery_key_hash, must_change_password, status)
            VALUES (?, ?, ?, 'Admin', ?, 0, 'Active');
            """,
            (username, pw_hash, pw_salt, rec_hash),
        )

        self.audit.log_event("USER_LOGIN_SUCCESS", username, "Initial setup wizard: Admin created", user_id=user_id)
        return True, "Administrator account and Master Recovery Key created successfully."

    def login(self, username: str, password: str) -> Tuple[bool, Optional[UserSession], str]:
        """Authenticate user with PBKDF2 hash checking and brute-force lockout guard."""
        username = sanitize_string(username, 30)
        if not username or not password:
            return False, None, "Please enter both username and password."

        user = self.db.fetch_one("SELECT * FROM users WHERE username = ?;", (username,))

        if not user:
            # Prevent timing enumeration and log failed attempt
            self.audit.log_event("USER_LOGIN_FAILED", username, "Login attempt for non-existent user")
            return False, None, "Invalid username or password."

        user_id = user["user_id"]
        role = user["role"]
        failed_attempts = user["failed_attempts"]
        locked_until_str = user["locked_until"]
        must_change = bool(user["must_change_password"])
        status = user["status"]

        # Check deactivated status
        if status == "Inactive":
            self.audit.log_event(
                "USER_LOGIN_FAILED", username, "Login rejected: Account is deactivated", user_id=user_id
            )
            return False, None, "Account is deactivated. Please contact an Administrator."

        # Check account lockout status
        now = datetime.now()
        if locked_until_str:
            try:
                locked_until = datetime.strptime(locked_until_str, "%Y-%m-%d %H:%M:%S")
                if now < locked_until:
                    remaining = int((locked_until - now).total_seconds())
                    return False, None, f"Account is temporarily locked. Please wait {remaining} seconds."
            except ValueError:
                pass  # Fall through if timestamp parsing fails

        # Verify PBKDF2 password
        is_valid_pw = verify_password(password, user["password_hash"], user["salt"])

        if not is_valid_pw:
            new_failed = failed_attempts + 1
            if new_failed >= MAX_FAILED_ATTEMPTS:
                lock_time = (now + timedelta(seconds=LOCKOUT_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
                self.db.execute(
                    "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE user_id = ?;",
                    (new_failed, lock_time, user_id),
                )
                self.audit.log_event("ACCOUNT_LOCKED", username, f"Account locked for {LOCKOUT_SECONDS}s after 5 failed tries", user_id=user_id)
                return False, None, f"Too many failed attempts. Account locked for {LOCKOUT_SECONDS} seconds."
            else:
                self.db.execute("UPDATE users SET failed_attempts = ? WHERE user_id = ?;", (new_failed, user_id))
                self.audit.log_event("USER_LOGIN_FAILED", username, f"Failed password attempt ({new_failed}/{MAX_FAILED_ATTEMPTS})", user_id=user_id)
                remaining_tries = MAX_FAILED_ATTEMPTS - new_failed
                return False, None, f"Invalid username or password. {remaining_tries} attempts remaining."

        # Successful authentication: reset failed attempts and unlock
        self.db.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE user_id = ?;", (user_id,))
        session = UserSession(
            user_id=user_id,
            username=username,
            role=role,
            must_change_password=must_change,
        )
        self.active_session = session
        self.audit.log_event("USER_LOGIN_SUCCESS", username, f"Successful login as {role}", user_id=user_id)
        return True, session, "Login successful."

    def logout(self):
        """Terminate the active session and log logout event."""
        if self.active_session:
            self.audit.log_event(
                "USER_LOGOUT",
                self.active_session.username,
                "User logged out",
                user_id=self.active_session.user_id,
            )
            self.active_session = None

    def reset_admin_with_master_key(
        self, master_recovery_key: str, new_password: str
    ) -> Tuple[bool, str]:
        """Emergency Admin Password Reset via the Master Recovery Key."""
        pw_valid, pw_msg = validate_password_strength(new_password)
        if not pw_valid:
            return False, pw_msg

        admin_row = self.db.fetch_one("SELECT * FROM users WHERE role = 'Admin' AND recovery_key_hash IS NOT NULL LIMIT 1;")
        if not admin_row:
            return False, "No Administrator with a Master Recovery Key was found."

        stored_rec_hash = admin_row["recovery_key_hash"]
        salt = admin_row["salt"]

        if not verify_recovery_key(master_recovery_key, stored_rec_hash, salt):
            self.audit.log_event("PASSWORD_RESET", admin_row["username"], "Failed recovery key verification", user_id=admin_row["user_id"])
            return False, "Invalid Master Recovery Key."

        new_hash, new_salt = hash_password(new_password)
        self.db.execute(
            """
            UPDATE users SET
                password_hash = ?,
                salt = ?,
                failed_attempts = 0,
                locked_until = NULL,
                must_change_password = 0
            WHERE user_id = ?;
            """,
            (new_hash, new_salt, admin_row["user_id"]),
        )
        self.audit.log_event("PASSWORD_RESET", admin_row["username"], "Admin password reset via Master Recovery Key", user_id=admin_row["user_id"])
        return True, "Administrator password has been successfully reset. Please log in with your new password."

    def admin_reset_staff_password(
        self, admin_session: UserSession, target_username: str, temp_password: str
    ) -> Tuple[bool, str]:
        """Admin resets a staff member's password and sets must_change_password = 1."""
        if not admin_session or not admin_session.is_admin():
            return False, "Access Denied: Only Administrators can reset staff passwords."

        target_username = sanitize_string(target_username, 30)
        target = self.db.fetch_one("SELECT * FROM users WHERE username = ?;", (target_username,))
        if not target:
            return False, f"User '{target_username}' not found."

        pw_valid, pw_msg = validate_password_strength(temp_password)
        if not pw_valid:
            return False, f"Temporary password does not meet policy: {pw_msg}"

        new_hash, new_salt = hash_password(temp_password)
        self.db.execute(
            """
            UPDATE users SET
                password_hash = ?,
                salt = ?,
                must_change_password = 1,
                failed_attempts = 0,
                locked_until = NULL
            WHERE user_id = ?;
            """,
            (new_hash, new_salt, target["user_id"]),
        )
        self.audit.log_event(
            "PASSWORD_RESET",
            admin_session.username,
            f"Admin reset password for user '{target_username}' (forced change required)",
            user_id=admin_session.user_id,
        )
        return True, f"Password for '{target_username}' reset successfully. User will be forced to change it on next login."

    def create_staff_account(
        self, admin_session: UserSession, username: str, temp_password: str, role: str = "Cashier"
    ) -> Tuple[bool, str]:
        """Admin creates a new staff account (Cashier) with must_change_password = 1."""
        if not admin_session or not admin_session.is_admin():
            return False, "Access Denied: Only Administrators can create staff accounts."

        username = sanitize_string(username, 30)
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters."

        existing = self.db.fetch_one("SELECT user_id FROM users WHERE username = ?;", (username,))
        if existing:
            return False, f"Username '{username}' already exists."

        pw_valid, pw_msg = validate_password_strength(temp_password)
        if not pw_valid:
            return False, f"Initial password does not meet policy: {pw_msg}"

        if role not in ("Admin", "Cashier"):
            return False, "Invalid role specified."

        pw_hash, pw_salt = hash_password(temp_password)
        user_id = self.db.execute(
            """
            INSERT INTO users (username, password_hash, salt, role, must_change_password, status)
            VALUES (?, ?, ?, ?, 1, 'Active');
            """,
            (username, pw_hash, pw_salt, role),
        )
        self.audit.log_event(
            "PASSWORD_RESET",
            admin_session.username,
            f"Created new {role} account '{username}' (forced change required)",
            user_id=admin_session.user_id,
        )
        return True, f"Staff account '{username}' created successfully."

    def change_user_password(
        self, username: str, current_password: str, new_password: str
    ) -> Tuple[bool, str]:
        """Change user password, verifying current password and setting must_change_password = 0."""
        user = self.db.fetch_one("SELECT * FROM users WHERE username = ?;", (username,))
        if not user:
            return False, "User not found."

        if not verify_password(current_password, user["password_hash"], user["salt"]):
            return False, "Current password is incorrect."

        pw_valid, pw_msg = validate_password_strength(new_password)
        if not pw_valid:
            return False, pw_msg

        new_hash, new_salt = hash_password(new_password)
        self.db.execute(
            """
            UPDATE users SET
                password_hash = ?,
                salt = ?,
                must_change_password = 0
            WHERE user_id = ?;
            """,
            (new_hash, new_salt, user["user_id"]),
        )
        if self.active_session and self.active_session.username == username:
            self.active_session.must_change_password = False

        self.audit.log_event("PASSWORD_RESET", username, "User changed password successfully", user_id=user["user_id"])
        return True, "Password updated successfully."

    def set_staff_status(
        self, admin_session: UserSession, target_username: str, new_status: str
    ) -> Tuple[bool, str]:
        """Admin activates or deactivates a staff member's account."""
        if not admin_session or not admin_session.is_admin():
            return False, "Access Denied: Only Administrators can modify account status."

        if new_status not in ("Active", "Inactive"):
            return False, f"Invalid status '{new_status}' specified."

        target_username = sanitize_string(target_username, 30)
        target = self.db.fetch_one("SELECT * FROM users WHERE username = ?;", (target_username,))
        if not target:
            return False, f"User '{target_username}' not found."

        if target["user_id"] == admin_session.user_id:
            return False, "Action Blocked: You cannot change the status of your own account."

        if target["role"] == "Admin" and new_status == "Inactive":
            admin_count = self.db.fetch_one(
                "SELECT COUNT(*) AS cnt FROM users WHERE role = 'Admin' AND status = 'Active';"
            )
            if admin_count and admin_count["cnt"] <= 1:
                return False, "Action Blocked: Cannot deactivate the sole Administrator."

        self.db.execute("UPDATE users SET status = ? WHERE user_id = ?;", (new_status, target["user_id"]))
        log_action = "ACCOUNT_LOCKED" if new_status == "Inactive" else "PASSWORD_RESET"
        self.audit.log_event(
            log_action,
            admin_session.username,
            f"Admin set account status of '{target_username}' to {new_status}",
            user_id=admin_session.user_id,
        )
        return True, f"Account '{target_username}' status successfully updated to {new_status}."

    def delete_staff_account(
        self, admin_session: UserSession, target_username: str
    ) -> Tuple[bool, str]:
        """Admin permanently deletes a staff account (if no historical invoices exist)."""
        if not admin_session or not admin_session.is_admin():
            return False, "Access Denied: Only Administrators can delete staff accounts."

        target_username = sanitize_string(target_username, 30)
        target = self.db.fetch_one("SELECT * FROM users WHERE username = ?;", (target_username,))
        if not target:
            return False, f"User '{target_username}' not found."

        if target["user_id"] == admin_session.user_id:
            return False, "Action Blocked: You cannot delete your own account."

        if target["role"] == "Admin":
            return False, "Action Blocked: Administrator accounts cannot be deleted here."

        # Check if cashier has processed invoices (foreign key preservation)
        bill_cnt = self.db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM bills WHERE cashier_id = ?;", (target["user_id"],)
        )
        if bill_cnt and bill_cnt["cnt"] > 0:
            return False, (
                f"Cannot delete '{target_username}': Staff member has processed {bill_cnt['cnt']} historical "
                f"invoice(s). In accordance with financial audit compliance, historical cashier records "
                f"must be preserved. Deactivate the account instead."
            )

        self.db.execute("DELETE FROM users WHERE user_id = ?;", (target["user_id"],))
        self.audit.log_event(
            "PASSWORD_RESET",
            admin_session.username,
            f"Admin permanently deleted staff account '{target_username}'",
            user_id=admin_session.user_id,
        )
        return True, f"Staff account '{target_username}' has been permanently deleted."


# Default singleton instance
auth_service = AuthService()
