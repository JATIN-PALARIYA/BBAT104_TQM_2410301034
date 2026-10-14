"""In-Memory Order Cart & Real-Time Financial Calculations [Review 2: POS Engine]
Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from src.security import validate_quantity


@dataclass
class CartItem:
    """Represents a single menu item in the POS order cart."""
    item_id: int
    item_name: str
    unit_price: float
    quantity: int = 1

    @property
    def line_total(self) -> float:
        return round(self.unit_price * self.quantity, 2)


class OrderCart:
    """Manages the in-memory shopping cart for the active cashier session."""

    def __init__(self):
        self._items: Dict[int, CartItem] = {}

    def add_item(self, item_id: int, item_name: str, unit_price: float, quantity: int = 1) -> Tuple[bool, str]:
        """Add an item or increment its quantity in the cart."""
        v_valid, valid_qty, msg = validate_quantity(quantity)
        if not v_valid:
            return False, f"Poka-Yoke Rejection: {msg}"

        if item_id in self._items:
            new_qty = self._items[item_id].quantity + valid_qty
            if new_qty > 999:
                return False, "Quantity limit exceeded (max 999)."
            self._items[item_id].quantity = new_qty
        else:
            self._items[item_id] = CartItem(
                item_id=item_id,
                item_name=item_name,
                unit_price=round(unit_price, 2),
                quantity=valid_qty,
            )
        return True, "Item added to cart."

    def update_quantity(self, item_id: int, quantity: int) -> Tuple[bool, str]:
        """Set specific quantity for a cart item; removes item if quantity is zero."""
        if item_id not in self._items:
            return False, "Item not found in cart."

        if quantity <= 0:
            del self._items[item_id]
            return True, "Item removed from cart."

        v_valid, valid_qty, msg = validate_quantity(quantity)
        if not v_valid:
            return False, f"Poka-Yoke Rejection: {msg}"

        self._items[item_id].quantity = valid_qty
        return True, "Quantity updated."

    def remove_item(self, item_id: int) -> bool:
        """Remove an item from the cart."""
        if item_id in self._items:
            del self._items[item_id]
            return True
        return False

    def clear(self):
        """Reset cart to empty state."""
        self._items.clear()

    @property
    def items(self) -> List[CartItem]:
        """Return list of current cart items."""
        return list(self._items.values())

    @property
    def is_empty(self) -> bool:
        """Check if cart has zero items."""
        return len(self._items) == 0

    def calculate_totals(self, discount_percent: float = 0.0, tax_rate: float = 0.05) -> Dict[str, float]:
        """Real-time financial calculation pipeline with 2-decimal precision.
        Menu item prices are inclusive of GST.
        """
        subtotal = round(sum(item.line_total for item in self._items.values()), 2)
        disc_rate = max(0.0, min(20.0, float(discount_percent)))
        discount_amount = round(subtotal * (disc_rate / 100.0), 2)
        final_total = round(subtotal - discount_amount, 2)

        effective_tax_rate = max(0.0, float(tax_rate))
        if effective_tax_rate > 0:
            taxable_amount = round(final_total / (1.0 + effective_tax_rate), 2)
            tax_amount = round(final_total - taxable_amount, 2)
        else:
            taxable_amount = final_total
            tax_amount = 0.0

        return {
            "subtotal": subtotal,
            "discount_percent": disc_rate,
            "discount_amount": discount_amount,
            "taxable_amount": taxable_amount,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "final_total": final_total,
        }
