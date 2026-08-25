ALTER TABLE apps ADD COLUMN IF NOT EXISTS no_price_seen_at timestamptz;

-- the failure counter has been ticking for every app steam answers with
-- data: [], which is most of the catalog. reset it now that an unpriced
-- answer counts as an answer.
UPDATE apps SET consecutive_failures = 0 WHERE consecutive_failures > 0;
