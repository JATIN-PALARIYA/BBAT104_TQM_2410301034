"""Menu Catalog CRUD Management Service [Review 2: Catalog Domain]
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
"""

from typing import Any, Dict, List, Optional, Tuple

from src.audit import audit_logger
from src.auth import UserSession
from src.database import db
from src.security import sanitize_string, validate_price

DEFAULT_CATEGORIES = [
    "Beverages",
    "Starters",
    "Main Course",
    "Desserts",
    "Breads & Rice",
]
VALID_CATEGORIES = DEFAULT_CATEGORIES


class MenuService:
    """Handles food catalog operations, category filtering, search, and Admin CRUD."""

    def __init__(self, db_manager=None, audit_engine=None):
        self.db = db_manager or db
        self.audit = audit_engine or audit_logger

    def get_categories(self) -> List[str]:
        """Return dynamic list of menu categories ordered by display order and name."""
        try:
            rows = self.db.fetch_all(
                "SELECT category_name FROM menu_categories ORDER BY display_order ASC, category_name ASC;"
            )
            if rows:
                return [r["category_name"] for r in rows]
        except Exception:
            pass
        return list(DEFAULT_CATEGORIES)

    def get_categories_with_counts(self) -> List[Dict[str, Any]]:
        """Return list of categories with their active/total item counts."""
        try:
            rows = self.db.fetch_all(
                """
                SELECT c.category_id, c.category_name, c.display_order,
                       COUNT(m.item_id) AS total_items,
                       SUM(CASE WHEN m.is_active = 1 THEN 1 ELSE 0 END) AS active_items
                FROM menu_categories c
                LEFT JOIN menu_items m ON c.category_name = m.category
                GROUP BY c.category_id, c.category_name, c.display_order
                ORDER BY c.display_order ASC, c.category_name ASC;
                """
            )
            return [
                {
                    "category_id": r["category_id"],
                    "category_name": r["category_name"],
                    "display_order": r["display_order"],
                    "total_items": int(r["total_items"] or 0),
                    "active_items": int(r["active_items"] or 0),
                }
                for r in rows
            ]
        except Exception:
            return [
                {
                    "category_id": i,
                    "category_name": name,
                    "display_order": i,
                    "total_items": 0,
                    "active_items": 0,
                }
                for i, name in enumerate(DEFAULT_CATEGORIES, 1)
            ]

    def add_category(self, admin_session: UserSession, category_name: str) -> Tuple[bool, str]:
        """Admin creates a new custom menu category with duplicate and empty name guards."""
        if not admin_session or not admin_session.is_admin():
            return False, "Access Denied: Only Administrators can create categories."

        category_name = sanitize_string(category_name, 40)
        if not category_name or len(category_name) < 2:
            return False, "Category name must be at least 2 characters long."

        if category_name.lower() == "all":
            return False, "'All' is a reserved filter name and cannot be used as a category."

        # Case-insensitive duplicate check
        existing = self.db.fetch_one(
            "SELECT category_name FROM menu_categories WHERE LOWER(category_name) = LOWER(?);",
            (category_name,),
        )
        if existing:
            return False, f"Category '{category_name}' already exists."

        max_order_row = self.db.fetch_one("SELECT MAX(display_order) FROM menu_categories;")
        next_order = ((max_order_row[0] if max_order_row else 0) or 0) + 1

        self.db.execute(
            "INSERT INTO menu_categories (category_name, display_order) VALUES (?, ?);",
            (category_name, next_order),
        )

        self.audit.log_event(
            "CATEGORY_ADDED",
            admin_session.username,
            f"Created menu category '{category_name}'",
            user_id=admin_session.user_id,
        )
        return True, f"Category '{category_name}' created successfully."

    def rename_category(
        self, admin_session: UserSession, old_name: str, new_name: str
    ) -> Tuple[bool, str]:
        """Admin renames a menu category, safely updating all existing items to prevent orphans."""
        if not admin_session or not admin_session.is_admin():
            return False, "Access Denied: Only Administrators can rename categories."

        old_name = old_name.strip()
        new_name = sanitize_string(new_name, 40)

        if not new_name or len(new_name) < 2:
            return False, "Category name must be at least 2 characters long."

        if new_name.lower() == "all":
            return False, "'All' is a reserved filter name and cannot be used as a category."

        if old_name.lower() == new_name.lower():
            return False, "New category name is identical to the current name."

        target_cat = self.db.fetch_one(
            "SELECT category_name FROM menu_categories WHERE category_name = ?;",
            (old_name,),
        )
        if not target_cat:
            return False, f"Category '{old_name}' not found."

        duplicate = self.db.fetch_one(
            "SELECT category_name FROM menu_categories WHERE LOWER(category_name) = LOWER(?) AND category_name != ?;",
            (new_name, old_name),
        )
        if duplicate:
            return False, f"A category named '{new_name}' already exists."

        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE menu_categories SET category_name = ? WHERE category_name = ?;",
                (new_name, old_name),
            )
            cur = conn.execute(
                """
                UPDATE menu_items SET
                    category = ?,
                    updated_at = DATETIME('now', 'localtime')
                WHERE category = ?;
                """,
                (new_name, old_name),
            )
            affected_items = cur.rowcount

        self.audit.log_event(
            "CATEGORY_RENAMED",
            admin_session.username,
            f"Renamed category '{old_name}' to '{new_name}' ({affected_items} menu items updated)",
            user_id=admin_session.user_id,
        )
        return True, f"Category renamed to '{new_name}' ({affected_items} items updated)."

    def delete_category(
        self, admin_session: UserSession, category_name: str, reassign_to: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Admin deletes a category, safely reassigning existing items to prevent orphaned records."""
        if not admin_session or not admin_session.is_admin():
            return False, "Access Denied: Only Administrators can delete categories."

        category_name = category_name.strip()

        target_cat = self.db.fetch_one(
            "SELECT category_name FROM menu_categories WHERE category_name = ?;",
            (category_name,),
        )
        if not target_cat:
            return False, f"Category '{category_name}' not found."

        total_cats_row = self.db.fetch_one("SELECT COUNT(*) FROM menu_categories;")
        total_cats = total_cats_row[0] if total_cats_row else 0
        if total_cats <= 1:
            return False, "Cannot delete the only remaining category in the system."

        cnt_row = self.db.fetch_one(
            "SELECT COUNT(*) FROM menu_items WHERE category = ?;",
            (category_name,),
        )
        item_count = cnt_row[0] if cnt_row else 0

        if item_count > 0:
            if not reassign_to or not reassign_to.strip():
                return False, f"Category '{category_name}' contains {item_count} menu items. Please select a destination category to reassign them to before deleting."

            reassign_to = reassign_to.strip()
            if reassign_to == category_name:
                return False, "Cannot reassign items to the category being deleted."

            dest_cat = self.db.fetch_one(
                "SELECT category_name FROM menu_categories WHERE category_name = ?;",
                (reassign_to,),
            )
            if not dest_cat:
                return False, f"Destination category '{reassign_to}' does not exist."

        with self.db.transaction() as conn:
            if item_count > 0 and reassign_to:
                conn.execute(
                    """
                    UPDATE menu_items SET
                        category = ?,
                        updated_at = DATETIME('now', 'localtime')
                    WHERE category = ?;
                    """,
                    (reassign_to, category_name),
                )
            conn.execute(
                "DELETE FROM menu_categories WHERE category_name = ?;",
                (category_name,),
            )

        details = f"Deleted category '{category_name}'"
        if item_count > 0 and reassign_to:
            details += f" (reassigned {item_count} items to '{reassign_to}')"

        self.audit.log_event(
            "CATEGORY_DELETED",
            admin_session.username,
            details,
            user_id=admin_session.user_id,
        )

        msg = f"Category '{category_name}' deleted successfully."
        if item_count > 0 and reassign_to:
            msg += f" {item_count} items reassigned to '{reassign_to}'."
        return True, msg

    def get_active_menu(
        self, category: Optional[str] = None, search_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve active menu items for Cashier POS counter, with optional filtering."""
        query = "SELECT item_id, item_name, category, price, is_active FROM menu_items WHERE is_active = 1"
        params: List[Any] = []

        if category and category != "All":
            query += " AND category = ?"
            params.append(category)

        if search_query and search_query.strip():
            query += " AND item_name LIKE ?"
            params.append(f"%{sanitize_string(search_query)}%")

        query += " ORDER BY category, item_name ASC;"
        rows = self.db.fetch_all(query, tuple(params))
        return [dict(r) for r in rows]

    def get_all_items_admin(self) -> List[Dict[str, Any]]:
        """Retrieve all menu items (including deactivated ones) for Admin management."""
        rows = self.db.fetch_all(
            "SELECT item_id, item_name, category, price, is_active, created_at, updated_at FROM menu_items ORDER BY item_id ASC;"
        )
        return [dict(r) for r in rows]

    def get_all_menu_items(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """Retrieve menu catalog items for exports, reporting, and API consumers."""
        if active_only:
            return self.get_active_menu()
        return self.get_all_items_admin()

    def get_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a single menu item by ID."""
        row = self.db.fetch_one(
            "SELECT item_id, item_name, category, price, is_active FROM menu_items WHERE item_id = ?;",
            (item_id,),
        )
        return dict(row) if row else None

    def add_menu_item(
        self, admin_session: UserSession, item_name: str, category: str, price_input: Any
    ) -> Tuple[bool, int, str]:
        """Admin creates a new menu item with Poka-Yoke price and category validation."""
        if not admin_session or not admin_session.is_admin():
            return False, 0, "Access Denied: Only Administrators can create menu items."

        item_name = sanitize_string(item_name, 60)
        if not item_name or len(item_name) < 2:
            return False, 0, "Item name must be at least 2 characters long."

        valid_cats = self.get_categories()
        if category not in valid_cats:
            return False, 0, f"Invalid category. Must be one of: {', '.join(valid_cats)}"

        p_valid, price, p_msg = validate_price(price_input)
        if not p_valid:
            return False, 0, f"Poka-Yoke Rejection: {p_msg}"

        existing = self.db.fetch_one("SELECT item_id FROM menu_items WHERE item_name = ?;", (item_name,))
        if existing:
            return False, 0, f"A menu item named '{item_name}' already exists."

        item_id = self.db.execute(
            """
            INSERT INTO menu_items (item_name, category, price, is_active)
            VALUES (?, ?, ?, 1);
            """,
            (item_name, category, price),
        )

        self.audit.log_event(
            "MENU_ITEM_ADDED",
            admin_session.username,
            f"Added item '{item_name}' [Cat: {category}, Price: ₹{price:.2f}]",
            user_id=admin_session.user_id,
        )
        return True, item_id, f"Menu item '{item_name}' added successfully."

    def update_menu_item(
        self, admin_session: UserSession, item_id: int, item_name: str, category: str, price_input: Any
    ) -> Tuple[bool, str]:
        """Admin updates an existing menu item's attributes."""
        if not admin_session or not admin_session.is_admin():
            return False, "Access Denied: Only Administrators can edit menu items."

        existing = self.get_item_by_id(item_id)
        if not existing:
            return False, f"Menu item with ID {item_id} not found."

        item_name = sanitize_string(item_name, 60)
        if not item_name or len(item_name) < 2:
            return False, "Item name must be at least 2 characters long."

        valid_cats = self.get_categories()
        if category not in valid_cats:
            return False, f"Invalid category. Must be one of: {', '.join(valid_cats)}"

        p_valid, price, p_msg = validate_price(price_input)
        if not p_valid:
            return False, f"Poka-Yoke Rejection: {p_msg}"

        # Ensure name uniqueness among other items
        duplicate = self.db.fetch_one(
            "SELECT item_id FROM menu_items WHERE item_name = ? AND item_id != ?;",
            (item_name, item_id),
        )
        if duplicate:
            return False, f"Another item named '{item_name}' already exists."

        self.db.execute(
            """
            UPDATE menu_items SET
                item_name = ?,
                category = ?,
                price = ?,
                updated_at = DATETIME('now', 'localtime')
            WHERE item_id = ?;
            """,
            (item_name, category, price, item_id),
        )

        self.audit.log_event(
            "MENU_ITEM_UPDATED",
            admin_session.username,
            f"Updated item #{item_id} '{item_name}' (Price: ₹{price:.2f}, Cat: {category})",
            user_id=admin_session.user_id,
        )
        return True, f"Menu item #{item_id} updated successfully."

    def toggle_item_status(
        self, admin_session: UserSession, item_id: int, is_active: bool
    ) -> Tuple[bool, str]:
        """Admin soft-deactivates or reactivates a menu item."""
        if not admin_session or not admin_session.is_admin():
            return False, "Access Denied: Only Administrators can modify item status."

        existing = self.get_item_by_id(item_id)
        if not existing:
            return False, f"Menu item with ID {item_id} not found."

        new_status = 1 if is_active else 0
        self.db.execute(
            """
            UPDATE menu_items SET
                is_active = ?,
                updated_at = DATETIME('now', 'localtime')
            WHERE item_id = ?;
            """,
            (new_status, item_id),
        )

        action_label = "MENU_ITEM_UPDATED" if is_active else "MENU_ITEM_DEACTIVATED"
        status_word = "Activated" if is_active else "Deactivated"

        self.audit.log_event(
            action_label,
            admin_session.username,
            f"{status_word} item #{item_id} '{existing['item_name']}'",
            user_id=admin_session.user_id,
        )
        return True, f"Item '{existing['item_name']}' successfully {status_word.lower()}."


# Default singleton instance
menu_service = MenuService()
