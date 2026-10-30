-- Owner can cancel orders that are awaiting approval or approved (decision #7, partial).
-- decided_at / decision_note are left as they were, so the approval history is kept.
ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'cancelled';

ALTER TABLE orders
  ADD COLUMN cancelled_at timestamptz,
  ADD COLUMN cancel_note text CHECK (length(cancel_note) BETWEEN 1 AND 1000);
