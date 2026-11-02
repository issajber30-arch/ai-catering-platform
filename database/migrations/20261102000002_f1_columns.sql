ALTER TABLE orders
  ADD COLUMN kitchen_at timestamptz,
  ADD COLUMN dispatched_at timestamptz,
  ADD COLUMN delivered_at timestamptz;

-- "Safety Car": the owner's manual switch for busy times; customers see a notice (public settings).
ALTER TABLE business_settings ADD COLUMN safety_car boolean NOT NULL DEFAULT false;

CREATE TABLE order_ratings (
  order_id uuid PRIMARY KEY REFERENCES orders(id) ON DELETE CASCADE,
  stars smallint NOT NULL CHECK (stars BETWEEN 1 AND 5),
  comment text CHECK (comment IS NULL OR length(comment) <= 500),
  created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE order_ratings ENABLE ROW LEVEL SECURITY;
