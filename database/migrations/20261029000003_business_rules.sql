-- Phase 3.1: owner-answered business rules (OPEN #5, #15, #19). One settings row, distance-based
-- delivery fee, geocode cache. delivery_zone_id stays (optional) for orders priced by zone.

CREATE TABLE business_settings (
  id boolean PRIMARY KEY DEFAULT true CHECK (id),
  lead_time_days int NOT NULL DEFAULT 7 CHECK (lead_time_days BETWEEN 0 AND 365),
  min_food_total numeric(10, 2) NOT NULL DEFAULT 500.00 CHECK (min_food_total >= 0),
  delivery_base_fee numeric(10, 2) NOT NULL DEFAULT 50.00 CHECK (delivery_base_fee >= 0),
  delivery_per_km numeric(10, 2) NOT NULL DEFAULT 4.00 CHECK (delivery_per_km >= 0),
  delivery_max_km numeric(6, 2) NOT NULL DEFAULT 40 CHECK (delivery_max_km BETWEEN 0 AND 500),
  kitchen_address text NOT NULL DEFAULT 'Jerusalem'
    CHECK (kitchen_address <> '' AND length(kitchen_address) <= 300),
  kitchen_lat double precision NOT NULL DEFAULT 31.7683,
  kitchen_lon double precision NOT NULL DEFAULT 35.2137
);
INSERT INTO business_settings DEFAULT VALUES;

-- Keyed by the lower-cased, whitespace-collapsed address. Not-found results are cached too.
CREATE TABLE geocode_cache (
  address_norm text PRIMARY KEY CHECK (length(address_norm) <= 500),
  lat double precision,
  lon double precision,
  found boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE orders
  ADD COLUMN delivery_km numeric(6, 2),
  ADD COLUMN delivery_lat double precision,
  ADD COLUMN delivery_lon double precision,
  ADD COLUMN delivery_fee_estimated boolean NOT NULL DEFAULT false;

ALTER TABLE orders DROP CONSTRAINT orders_check;
ALTER TABLE orders ADD CONSTRAINT orders_delivery_needs_address CHECK (
  fulfillment_type <> 'delivery' OR (delivery_address IS NOT NULL AND delivery_address <> '')
);

ALTER TABLE business_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE geocode_cache ENABLE ROW LEVEL SECURITY;
