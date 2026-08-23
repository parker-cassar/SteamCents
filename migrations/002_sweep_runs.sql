CREATE TABLE IF NOT EXISTS sweep_runs (
  id           bigserial PRIMARY KEY,
  started_at   timestamptz NOT NULL DEFAULT now(),
  heartbeat_at timestamptz NOT NULL DEFAULT now(),
  ended_at     timestamptz,
  exit_reason  text,
  batches      integer NOT NULL DEFAULT 0,
  apps_checked integer NOT NULL DEFAULT 0,
  changes      integer NOT NULL DEFAULT 0,
  http_429s    integer NOT NULL DEFAULT 0,
  errors       integer NOT NULL DEFAULT 0
);

ALTER TABLE apps ADD COLUMN IF NOT EXISTS consecutive_failures smallint NOT NULL DEFAULT 0;

-- appids that keep coming back with nothing drop out of the queue, otherwise a
-- few hundred dead ones round trip forever and eat the request budget
DROP INDEX IF EXISTS apps_sweep;
CREATE INDEX apps_sweep
  ON apps (last_checked_at NULLS FIRST)
  WHERE delisted_at IS NULL AND consecutive_failures < 5;
