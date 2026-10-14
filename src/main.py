"""
Application Bootstrapper and Desktop GUI Entry Point.
Initializes secure SQLite connection, cryptographic key manager,
tamper-evident audit trail, authentication, menu catalog, and billing services.
"""
import sys
import os

# Ensure project root is in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.database.manager import DatabaseManager
from src.audit.logger import AuditLogger
from src.auth.service import AuthService
from src.menu.service import MenuService
from src.billing.service import BillingService
from src.billing.exporter import ExportService
from src.gui.main_window import MainWindow


def bootstrap_application():
    """Initializes service container, seeds defaults if needed, and launches desktop GUI."""
    db_path = os.path.join(ROOT_DIR, "db", "restaurant_pos.db")

    # 1. Database & Schema
    db = DatabaseManager(db_path=db_path)
    db.initialize_schema()

    # 2. Tamper-evident Audit Logger
    audit_logger = AuditLogger(db_manager=db)

    # 3. Domain Services
    auth_service = AuthService(db_manager=db, audit_engine=audit_logger)
    menu_service = MenuService(db_manager=db, audit_engine=audit_logger)
    billing_service = BillingService(db_manager=db, audit_engine=audit_logger)
    export_service = ExportService(db_manager=db, billing_engine=billing_service, menu_engine=menu_service)

    # 4. Bootstrap default accounts if first run
    if auth_service.is_setup_needed():
        auth_service.initial_setup_admin("admin", "AdminPass@2026", "MasterKey@Secret99")
        ok, admin_sess, _ = auth_service.login("admin", "AdminPass@2026")
        if ok and admin_sess:
            auth_service.create_staff_account(admin_sess, "cashier1", "CashierPass@2026", "Cashier")
            auth_service.logout()

    # 5. Launch Desktop Presentation Layer
    app = MainWindow(
        db_manager=db,
        auth_service=auth_service,
        menu_service=menu_service,
        billing_service=billing_service,
        export_service=export_service,
        audit_logger=audit_logger
    )
    return app


def main():
    """Main CLI / Desktop execution entry point."""
    try:
        app = bootstrap_application()
        app.mainloop()
    except Exception as ex:
        print(f"Fatal error during application startup: {ex}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
