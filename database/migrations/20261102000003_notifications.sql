-- F1 PR6: opt-in SMS/WhatsApp updates (Twilio). One row per (order, kind, channel) = sent at most once.
ALTER TABLE orders
  ADD COLUMN sms_opt_in boolean NOT NULL DEFAULT false,
  ADD COLUMN lang text NOT NULL DEFAULT 'he' CHECK (lang IN ('he', 'ar', 'en'));

CREATE TABLE notifications (
  order_id uuid NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('flying_lap', 'safety_car')),
  channel text NOT NULL CHECK (channel IN ('sms', 'whatsapp')),
  status text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (order_id, kind, channel)
);
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
