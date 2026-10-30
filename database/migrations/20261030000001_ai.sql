-- Phase 4: AI assistant. One conversation per order; the assistant only proposes changes and
-- the customer approves them (docs/AI_AGENT_DESIGN.md).

CREATE TYPE proposal_status AS ENUM ('pending', 'approved', 'rejected', 'expired', 'failed');

CREATE TABLE ai_conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id uuid NOT NULL UNIQUE REFERENCES orders (id),
  created_at timestamptz NOT NULL DEFAULT now()
);

-- content: {"text": ...} for user rows, the API content-block list for assistant and tool rows.
-- seq gives a stable order even when created_at ties. Usage columns are set on assistant rows.
CREATE TABLE ai_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES ai_conversations (id),
  seq bigint GENERATED ALWAYS AS IDENTITY,
  role text NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
  content jsonb NOT NULL,
  input_tokens int,
  output_tokens int,
  cache_read_tokens int,
  cache_creation_tokens int,
  stop_reason text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ai_messages_conversation_seq ON ai_messages (conversation_id, seq);

CREATE TABLE ai_change_proposals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id uuid NOT NULL REFERENCES orders (id),
  conversation_id uuid REFERENCES ai_conversations (id),
  base_order_version int NOT NULL,
  changes jsonb NOT NULL,
  diff jsonb NOT NULL,
  rationale text CHECK (length(rationale) <= 1000),
  price_before numeric(10, 2) NOT NULL,
  price_after numeric(10, 2) NOT NULL,
  status proposal_status NOT NULL DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now(),
  decided_at timestamptz,
  executed_at timestamptz
);
CREATE INDEX ai_change_proposals_order ON ai_change_proposals (order_id);
CREATE UNIQUE INDEX ai_change_proposals_one_pending
  ON ai_change_proposals (order_id) WHERE status = 'pending';

ALTER TABLE ai_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_change_proposals ENABLE ROW LEVEL SECURITY;
