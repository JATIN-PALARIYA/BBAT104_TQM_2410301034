-- =============================================================================
-- Restaurant Billing System with Enhanced Security Architecture [Q04]
-- Relational Database Initial Seed Data
-- Course: BBAT104 (Fundamentals of TQM) | Student: Jatin Palariya (2410301034)
-- =============================================================================

-- Default System Settings
INSERT OR IGNORE INTO app_settings (setting_key, setting_value, updated_at) VALUES
    ('tax_rate', '0.05', DATETIME('now', 'localtime')),
    ('restaurant_name', 'Amrapali Campus Diner', DATETIME('now', 'localtime')),
    ('currency_symbol', '₹', DATETIME('now', 'localtime')),
    ('max_failed_attempts', '5', DATETIME('now', 'localtime')),
    ('lockout_duration_seconds', '60', DATETIME('now', 'localtime'));

-- Default Baseline Menu Categories
INSERT OR IGNORE INTO menu_categories (category_id, category_name, display_order) VALUES
    (1, 'Beverages', 1),
    (2, 'Starters', 2),
    (3, 'Main Course', 3),
    (4, 'Desserts', 4),
    (5, 'Breads & Rice', 5);

-- Default Baseline Menu Catalog Items
INSERT OR IGNORE INTO menu_items (item_id, item_name, category, price, is_active, created_at, updated_at) VALUES
    (1, 'Masala Chai', 'Beverages', 30.00, 1, DATETIME('now', 'localtime'), DATETIME('now', 'localtime')),
    (2, 'Cold Coffee', 'Beverages', 80.00, 1, DATETIME('now', 'localtime'), DATETIME('now', 'localtime')),
    (3, 'Paneer Tikka', 'Starters', 220.00, 1, DATETIME('now', 'localtime'), DATETIME('now', 'localtime')),
    (4, 'Veg Spring Rolls', 'Starters', 150.00, 1, DATETIME('now', 'localtime'), DATETIME('now', 'localtime')),
    (5, 'Dal Makhani', 'Main Course', 240.00, 1, DATETIME('now', 'localtime'), DATETIME('now', 'localtime')),
    (6, 'Butter Paneer Masala', 'Main Course', 280.00, 1, DATETIME('now', 'localtime'), DATETIME('now', 'localtime')),
    (7, 'Tandoori Roti', 'Breads & Rice', 20.00, 1, DATETIME('now', 'localtime'), DATETIME('now', 'localtime')),
    (8, 'Butter Naan', 'Breads & Rice', 45.00, 1, DATETIME('now', 'localtime'), DATETIME('now', 'localtime')),
    (9, 'Jeera Rice', 'Breads & Rice', 140.00, 1, DATETIME('now', 'localtime'), DATETIME('now', 'localtime')),
    (10, 'Gulab Jamun (2 pcs)', 'Desserts', 70.00, 1, DATETIME('now', 'localtime'), DATETIME('now', 'localtime'));
