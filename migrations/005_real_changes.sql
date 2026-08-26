-- last_changed_at was stamped on the very first observation too, so every app
-- that had ever been priced looked like it had just moved and landed in the
-- fastest tier. only a second observation onward is an actual change.
UPDATE apps a
SET last_changed_at = NULL
WHERE last_changed_at IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM price_observations o
    WHERE o.appid = a.appid
    GROUP BY o.appid HAVING count(*) > 1
  );

UPDATE apps a
SET last_changed_at = o.latest
FROM (
  SELECT appid, max(observed_at) AS latest
  FROM price_observations GROUP BY appid HAVING count(*) > 1
) o
WHERE o.appid = a.appid;
