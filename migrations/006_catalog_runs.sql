CREATE TABLE IF NOT EXISTS catalog_runs (
  id             bigserial PRIMARY KEY,
  started_at     timestamptz NOT NULL DEFAULT now(),
  ended_at       timestamptz,
  exit_reason    text,
  remote_apps    integer NOT NULL DEFAULT 0,
  total          integer NOT NULL DEFAULT 0,
  live           integer NOT NULL DEFAULT 0,
  newly_delisted integer NOT NULL DEFAULT 0,
  note           text
);
