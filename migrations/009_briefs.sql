CREATE TABLE IF NOT EXISTS briefs (
  id             bigserial PRIMARY KEY,
  period_start   date NOT NULL,
  period_end     date NOT NULL,
  facts_json     jsonb NOT NULL,
  brief_json     jsonb NOT NULL,
  model          text NOT NULL,
  prompt_version text NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (period_start, period_end, prompt_version)
);

CREATE INDEX IF NOT EXISTS briefs_created_at ON briefs (created_at DESC);
