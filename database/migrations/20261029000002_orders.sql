-- Phase 3: customers, events, orders, order items, serving-quantity rules.
-- Guest checkout: no accounts yet (OPEN #1), so customers has no auth_user_id; orders carry a
-- hashed private access token instead.

CREATE TYPE order_status AS ENUM ('draft', 'pending_approval', 'approved', 'rejected');

CREATE TABLE customers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name text NOT NULL CHECK (full_name <> '' AND length(full_name) <= 200),
  email text CHECK (length(email) <= 254),
  phone text CHECK (length(phone) <= 50),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (email IS NOT NULL OR phone IS NOT NULL)
);

-- Dietary counts are subsets of adults + children (decision #4).
CREATE TABLE events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id uuid NOT NULL REFERENCES customers (id),
  event_type text NOT NULL CHECK (event_type <> '' AND length(event_type) <= 100),
  event_date date NOT NULL,
  adults int NOT NULL CHECK (adults >= 0),
  children int NOT NULL CHECK (children >= 0),
  vegetarian_guests int NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),
  vegan_guests int NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),
  restricted_guests int NOT NULL DEFAULT 0 CHECK (restricted_guests >= 0),
  dietary_notes text CHECK (length(dietary_notes) <= 2000),
  CHECK (adults + children > 0),
  CHECK (vegetarian_guests <= adults + children),
  CHECK (vegan_guests <= adults + children),
  CHECK (restricted_guests <= adults + children)
);

CREATE TABLE orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id uuid NOT NULL REFERENCES customers (id),
  event_id uuid NOT NULL UNIQUE REFERENCES events (id),
  status order_status NOT NULL DEFAULT 'draft',
  version int NOT NULL DEFAULT 1,
  access_token_hash text NOT NULL,
  fulfillment_type fulfillment_type NOT NULL,
  time_slot_id uuid REFERENCES time_slots (id) ON DELETE SET NULL,
  requested_at timestamptz NOT NULL,
  delivery_address text CHECK (length(delivery_address) <= 500),
  delivery_zone_id uuid REFERENCES delivery_zones (id),
  currency char(3) NOT NULL,
  subtotal numeric(10, 2),
  delivery_fee numeric(10, 2),
  total numeric(10, 2),
  submitted_at timestamptz,
  decided_at timestamptz,
  decision_note text CHECK (length(decision_note) <= 1000),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (
    fulfillment_type <> 'delivery'
    OR (delivery_address IS NOT NULL AND delivery_address <> '' AND delivery_zone_id IS NOT NULL)
  )
);
CREATE INDEX orders_customer_id_idx ON orders (customer_id);
CREATE INDEX orders_status_idx ON orders (status);

CREATE TABLE order_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id uuid NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
  dish_id uuid NOT NULL REFERENCES dishes (id),
  quantity numeric(10, 2) NOT NULL CHECK (quantity > 0),
  snapshot_name text,
  snapshot_pricing_unit pricing_unit,
  snapshot_unit_price numeric(10, 2),
  snapshot_line_total numeric(10, 2),
  UNIQUE (order_id, dish_id)
);
CREATE INDEX order_items_order_id_idx ON order_items (order_id);

-- Owner-configured serving rules (decision #3). No rule for a category = no recommendation.
CREATE TABLE quantity_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id uuid NOT NULL UNIQUE REFERENCES dish_categories (id) ON DELETE CASCADE,
  per_adult numeric(10, 3) NOT NULL CHECK (per_adult >= 0),
  per_child numeric(10, 3) NOT NULL CHECK (per_child >= 0),
  round_step numeric(10, 3) NOT NULL DEFAULT 1 CHECK (round_step > 0)
);

ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE quantity_rules ENABLE ROW LEVEL SECURITY;
