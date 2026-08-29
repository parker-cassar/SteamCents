-- always false, was never populated. filters=price_overview on the sweep
-- request means steam never sends is_free, and no_price_seen_at already
-- covers "this app has no price" regardless of why.
ALTER TABLE apps DROP COLUMN IF EXISTS is_free;
