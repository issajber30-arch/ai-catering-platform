-- Demo data for a local SQLite database (never for Postgres/production).
-- First build the tables:  DATABASE_URL=sqlite:///./caterking_dev.db uv run python -m app.migrate
-- Then, from backend/:     sqlite3 caterking_dev.db < ../database/sqlite/demo_seed.sql
-- Safe to re-run (INSERT OR IGNORE on fixed ids). Ids are UUIDs in SQLAlchemy's SQLite form
-- (32 hex chars, no dashes); times are UTC and given explicitly, because the app's now() and
-- gen_random_uuid() exist only inside the app's connections, not in the sqlite3 shell.
PRAGMA foreign_keys = ON;
BEGIN;

INSERT OR IGNORE INTO dish_categories (id, name_he, name_ar, name_en, sort_order, is_active) VALUES
  ('c0000000000000000000000000000001', 'סלטים', 'سلطات', 'Salads', 1, 1),
  ('c0000000000000000000000000000002', 'עיקריות', 'أطباق رئيسية', 'Mains', 2, 1),
  ('c0000000000000000000000000000003', 'קינוחים', 'حلويات', 'Desserts', 3, 1);

INSERT OR IGNORE INTO dishes (id, category_id, name_he, name_ar, name_en, description_he, description_en,
  pricing_unit, unit_price, unit_label, currency, min_quantity, is_available, created_at, updated_at) VALUES
  ('d0000000000000000000000000000001', 'c0000000000000000000000000000001', 'סלט ירקות', 'سلطة خضار', 'Garden salad',
   'ירקות טריים חתוכים דק', 'Fresh finely chopped vegetables', 'per_tray', 90, 'מגש', 'ILS', NULL, 1, '2026-11-02 09:00:00.000000', '2026-11-02 09:00:00.000000'),
  ('d0000000000000000000000000000002', 'c0000000000000000000000000000001', 'חומוס', 'حمص', 'Hummus',
   'חומוס ביתי עם טחינה', 'Home-made hummus with tahini', 'per_tray', 70, 'מגש', 'ILS', NULL, 1, '2026-11-02 09:00:00.000000', '2026-11-02 09:00:00.000000'),
  ('d0000000000000000000000000000003', 'c0000000000000000000000000000002', 'שניצל', 'شنيتسل', 'Schnitzel',
   'חזה עוף בציפוי פירורי לחם', 'Breaded chicken breast', 'per_tray', 120, 'מגש', 'ILS', 2, 1, '2026-11-02 09:00:00.000000', '2026-11-02 09:00:00.000000'),
  ('d0000000000000000000000000000004', 'c0000000000000000000000000000002', 'פרגיות על האש', 'دجاج مشوي', 'Grilled chicken thighs',
   NULL, NULL, 'per_weight', 140, 'ק"ג', 'ILS', 1, 1, '2026-11-02 09:00:00.000000', '2026-11-02 09:00:00.000000'),
  ('d0000000000000000000000000000005', 'c0000000000000000000000000000002', 'אורז לבן', 'أرز أبيض', 'White rice',
   NULL, NULL, 'per_tray', 60, 'מגש', 'ILS', NULL, 1, '2026-11-02 09:00:00.000000', '2026-11-02 09:00:00.000000'),
  ('d0000000000000000000000000000006', 'c0000000000000000000000000000003', 'עוגת שוקולד', 'كعكة شوكولاتة', 'Chocolate cake',
   NULL, NULL, 'per_item', 85, 'עוגה', 'ILS', NULL, 1, '2026-11-02 09:00:00.000000', '2026-11-02 09:00:00.000000'),
  ('d0000000000000000000000000000007', 'c0000000000000000000000000000003', 'סלט פירות', 'سلطة فواكه', 'Fruit salad',
   NULL, NULL, 'per_guest', 12, NULL, 'ILS', NULL, 1, '2026-11-02 09:00:00.000000', '2026-11-02 09:00:00.000000');

-- Missing rows/NULLs mean "unknown" (never "no"): the rice has no dietary row on purpose.
INSERT OR IGNORE INTO dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan) VALUES
  ('d0000000000000000000000000000001', 'pareve', 1, 1),
  ('d0000000000000000000000000000002', 'pareve', 1, 1),
  ('d0000000000000000000000000000003', 'meat', 0, 0),
  ('d0000000000000000000000000000004', 'meat', 0, 0),
  ('d0000000000000000000000000000006', 'dairy', 1, 0),
  ('d0000000000000000000000000000007', 'pareve', 1, 1);

INSERT OR IGNORE INTO dish_allergens (dish_id, allergen_id, status)
  SELECT d, (SELECT id FROM allergens WHERE name = a), s FROM (
    SELECT 'd0000000000000000000000000000002' AS d, 'sesame' AS a, 'contains' AS s
    UNION ALL SELECT 'd0000000000000000000000000000003', 'gluten', 'contains'
    UNION ALL SELECT 'd0000000000000000000000000000003', 'eggs', 'contains'
    UNION ALL SELECT 'd0000000000000000000000000000006', 'milk', 'contains'
    UNION ALL SELECT 'd0000000000000000000000000000006', 'eggs', 'contains'
    UNION ALL SELECT 'd0000000000000000000000000000006', 'gluten', 'contains'
    UNION ALL SELECT 'd0000000000000000000000000000001', 'peanuts', 'free');

INSERT OR IGNORE INTO quantity_rules (id, category_id, per_adult, per_child, round_step) VALUES
  ('a0000000000000000000000000000001', 'c0000000000000000000000000000002', 0.1, 0.05, 1);

INSERT OR IGNORE INTO time_slots (id, fulfillment_type, weekday, start_time, end_time, capacity, is_active) VALUES
  ('e0000000000000000000000000000001', 'pickup', NULL, '12:00:00.000000', '14:00:00.000000', NULL, 1),
  ('e0000000000000000000000000000002', 'delivery', NULL, '18:00:00.000000', '20:00:00.000000', 5, 1);

INSERT OR IGNORE INTO delivery_zones (id, name, fee, definition, is_active) VALUES
  ('f0000000000000000000000000000001', 'ירושלים', 50, '{}', 1);

INSERT OR IGNORE INTO blocked_dates (id, date, reason) VALUES
  ('b0000000000000000000000000000001', '2026-12-31', 'סגור לאירוע פרטי');

-- One order waiting for the owner's approval: 3 × Schnitzel + 2 × Garden salad + 1 × Chocolate cake.
INSERT OR IGNORE INTO customers (id, full_name, email, phone, created_at, updated_at) VALUES
  ('10000000000000000000000000000001', 'דנה כהן (דמו)', 'dana.demo@example.com', NULL, '2026-11-02 09:00:00.000000', '2026-11-02 09:00:00.000000');

INSERT OR IGNORE INTO events (id, customer_id, event_type, event_date, adults, children,
  vegetarian_guests, vegan_guests, restricted_guests, dietary_notes) VALUES
  ('20000000000000000000000000000001', '10000000000000000000000000000001', 'birthday', '2026-11-16',
   30, 10, 4, 1, 0, 'בלי בוטנים בבקשה');

-- access_token_hash matches no token, so this demo order has no customer link (owner view only).
INSERT OR IGNORE INTO orders (id, customer_id, event_id, status, version, access_token_hash,
  fulfillment_type, time_slot_id, requested_at, delivery_fee_estimated, currency,
  subtotal, delivery_fee, total, submitted_at, first_submitted_at, created_at, updated_at) VALUES
  ('30000000000000000000000000000001', '10000000000000000000000000000001', '20000000000000000000000000000001',
   'pending_approval', 3, '0000000000000000000000000000000000000000000000000000000000000000',
   'pickup', 'e0000000000000000000000000000001', '2026-11-16 10:00:00.000000', 0, 'ILS',
   625, 0, 625, '2026-11-02 09:00:00.000000', '2026-11-02 09:00:00.000000', '2026-11-02 09:00:00.000000', '2026-11-02 09:00:00.000000');

INSERT OR IGNORE INTO order_items (id, order_id, dish_id, quantity, snapshot_name,
  snapshot_pricing_unit, snapshot_unit_price, snapshot_line_total) VALUES
  ('40000000000000000000000000000001', '30000000000000000000000000000001', 'd0000000000000000000000000000003', 3, 'שניצל', 'per_tray', 120, 360),
  ('40000000000000000000000000000002', '30000000000000000000000000000001', 'd0000000000000000000000000000001', 2, 'סלט ירקות', 'per_tray', 90, 180),
  ('40000000000000000000000000000003', '30000000000000000000000000000001', 'd0000000000000000000000000000006', 1, 'עוגת שוקולד', 'per_item', 85, 85);

COMMIT;
