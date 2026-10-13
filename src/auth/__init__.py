"""Authentication, RBAC & Lockout Protection Package [Q04: Security Core]
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
"""

from src.auth.service import AuthService, auth_service
from src.auth.session import UserSession, require_role

__all__ = [
    "UserSession",
    "require_role",
    "AuthService",
    "auth_service",
]
