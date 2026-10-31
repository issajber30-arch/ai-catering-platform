-- Customers may change an order until N hours before the event; it then returns to the owner.
ALTER TABLE business_settings
  ADD COLUMN edit_cutoff_hours int NOT NULL DEFAULT 4 CHECK (edit_cutoff_hours BETWEEN 0 AND 168);

ALTER TABLE orders
  ADD COLUMN first_submitted_at timestamptz,
  ADD COLUMN reopened_at timestamptz;

UPDATE orders SET first_submitted_at = submitted_at WHERE submitted_at IS NOT NULL;
