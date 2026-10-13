"""User Session & RBAC Decorator Models [Q04: Security & RBAC]
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class UserSession:
    """Represents an active authenticated user session."""
    user_id: int
    username: str
    role: str  # 'Admin' or 'Cashier'
    must_change_password: bool

    def is_admin(self) -> bool:
        return self.role == "Admin"

    def is_cashier(self) -> bool:
        return self.role == "Cashier"


def require_role(allowed_role: str):
    """Decorator guarding functions to enforce Role-Based Access Control."""
    def decorator(func: Callable):
        def wrapper(self, *args, **kwargs):
            session: Optional[UserSession] = getattr(self, "current_session", None)
            if not session:
                raise PermissionError("Access Denied: No active authenticated session.")
            if session.role != allowed_role:
                raise PermissionError(f"Access Denied: Requires '{allowed_role}' role privileges.")
            return func(self, *args, **kwargs)
        return wrapper
    return decorator
