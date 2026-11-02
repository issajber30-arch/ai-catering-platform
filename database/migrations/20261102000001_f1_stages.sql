-- Kitchen/delivery stages after approval. Alone in its file: a new enum value cannot be used in
-- the transaction that adds it, and the migration runner wraps each file in one transaction.
ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'in_kitchen';
ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'out_for_delivery';
ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'ready_for_pickup';
ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'delivered';
