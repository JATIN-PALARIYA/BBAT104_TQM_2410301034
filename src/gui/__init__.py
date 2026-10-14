"""
Desktop GUI Presentation Layer for BBAT104 Restaurant Billing System.
Follows 3-Tier MVC architecture with role-aware view navigation.
"""
from src.gui.main_window import MainWindow
from src.gui.login_dialog import LoginDialog

__all__ = ["MainWindow", "LoginDialog"]
