CREATE TABLE IF NOT EXISTS apps (
  appid           integer PRIMARY KEY,
  name            text NOT NULL,
  app_type        text,
  is_free         boolean NOT NULL DEFAULT false,
  first_seen_at   timestamptz NOT NULL DEFAULT now(),
  last_seen_at    timestamptz NOT NULL DEFAULT now(),
  delisted_at     timestamptz,
  last_checked_at timestamptz,
  last_changed_at timestamptz
);

-- order in new (null) apps then oldest ones since yk ascending
CREATE INDEX IF NOT EXISTS apps_sweep
  ON apps (last_checked_at NULLS FIRST)
  WHERE delisted_at IS NULL;

CREATE TABLE IF NOT EXISTS price_observations (
  appid          integer NOT NULL REFERENCES apps(appid),
  country_code   char(2) NOT NULL DEFAULT 'us',
  observed_at    timestamptz NOT NULL,
  currency       char(3) NOT NULL,
  initial_cents  integer NOT NULL,
  final_cents    integer NOT NULL,
  discount_pct   smallint NOT NULL,
  PRIMARY KEY (appid, country_code, observed_at)
);
