CREATE INDEX IF NOT EXISTS price_observations_observed_at
  ON price_observations (observed_at DESC);

CREATE OR REPLACE VIEW app_latest_price AS
SELECT DISTINCT ON (appid, country_code)
  appid, country_code, observed_at, currency,
  initial_cents, final_cents, discount_pct
FROM price_observations
ORDER BY appid, country_code, observed_at DESC;

-- a row only exists when the price differed from the one before it, so every
-- row with a predecessor is a real change and the first one is just first sight
CREATE OR REPLACE VIEW price_changes AS
SELECT
  appid, country_code, observed_at, currency,
  initial_cents, final_cents, discount_pct,
  lag(final_cents)   OVER w AS prev_final_cents,
  lag(discount_pct)  OVER w AS prev_discount_pct
FROM price_observations
WINDOW w AS (PARTITION BY appid, country_code ORDER BY observed_at);

CREATE OR REPLACE VIEW price_changes_daily AS
SELECT
  observed_at::date AS day,
  country_code,
  count(*) AS changes,
  count(*) FILTER (WHERE final_cents < prev_final_cents) AS drops,
  count(*) FILTER (WHERE final_cents > prev_final_cents) AS rises,
  count(DISTINCT appid) AS apps
FROM price_changes
WHERE prev_final_cents IS NOT NULL
GROUP BY 1, 2;

CREATE OR REPLACE VIEW price_drops AS
SELECT
  c.appid, a.name, c.country_code, c.observed_at, c.currency,
  c.prev_final_cents, c.final_cents, c.discount_pct,
  c.prev_final_cents - c.final_cents AS drop_cents,
  round(100.0 * (c.prev_final_cents - c.final_cents) / c.prev_final_cents, 1) AS drop_pct
FROM price_changes c
JOIN apps a USING (appid)
WHERE c.prev_final_cents IS NOT NULL
  AND c.prev_final_cents > 0
  AND c.final_cents < c.prev_final_cents;
