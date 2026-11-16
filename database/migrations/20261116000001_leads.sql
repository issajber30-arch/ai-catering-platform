-- Leads: potential customers scored by a clipped linear regression (services/lead_model.py).
-- Name/contact/notes are stored for the owner only; the model never reads them.
CREATE TABLE leads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name text NOT NULL CHECK (length(full_name) BETWEEN 1 AND 200),
  phone text CHECK (length(phone) <= 40),
  email text CHECK (length(email) <= 200),
  notes text CHECK (length(notes) <= 2000),
  event_type text NOT NULL
    CHECK (event_type IN ('birthday', 'family_celebration', 'bar_bat_mitzvah', 'shabbat', 'other')),
  event_date date NOT NULL,
  guests integer NOT NULL CHECK (guests BETWEEN 1 AND 1000),
  source text NOT NULL
    CHECK (source IN ('instagram', 'google', 'referral', 'whatsapp', 'phone', 'other')),
  returning_customer boolean NOT NULL DEFAULT false,
  used_assistant boolean NOT NULL DEFAULT false,
  requested_quote boolean NOT NULL DEFAULT false,
  budget_per_guest numeric(10,2) CHECK (budget_per_guest >= 0),
  currency char(3) NOT NULL DEFAULT 'ILS',
  status text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'won', 'lost')),
  is_demo boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX leads_status_created_idx ON leads (status, created_at);
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
