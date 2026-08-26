ALTER TABLE apps ADD COLUMN IF NOT EXISTS tier smallint NOT NULL DEFAULT 1;
ALTER TABLE apps ADD COLUMN IF NOT EXISTS next_due_at timestamptz NOT NULL DEFAULT 'epoch';

UPDATE apps SET next_due_at = coalesce(last_checked_at, 'epoch');

-- epoch instead of null so apps the catalog sync just added sort first without
-- the claim needing NULLS FIRST, which a plain btree cannot serve
DROP INDEX IF EXISTS apps_sweep;
CREATE INDEX apps_sweep
  ON apps (next_due_at)
  WHERE delisted_at IS NULL;
