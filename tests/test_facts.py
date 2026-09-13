from steamprice import config, facts


def seed_drop(conn, appid, name, prev, final):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO apps (appid, name) VALUES (%s, %s)", (appid, name))
        cur.execute("""
            INSERT INTO price_observations
              (appid, country_code, observed_at, currency, initial_cents,
               final_cents, discount_pct)
            VALUES
              (%s, %s, now() - interval '2 days', 'USD', %s, %s, 0),
              (%s, %s, now() - interval '1 day', 'USD', %s, %s, 0)
        """, (appid, config.COUNTRY, prev, prev, appid, config.COUNTRY, final, final))
        cur.execute("""
            INSERT INTO sweep_runs (apps_checked, changes, http_429s, errors)
            VALUES (100, 1, 0, 0)
        """)
    conn.commit()


def test_build_facts_includes_drops(conn):
    seed_drop(conn, 10, "Fine Game", 2000, 1000)
    with conn.cursor() as cur:
        payload = facts.build_facts(cur, days=7)
    assert payload["catalog"]["live"] == 1
    assert payload["period"]["checks"] == 100
    assert len(payload["top_drops"]) == 1
    assert payload["top_drops"][0]["appid"] == 10
    assert "period_start" in payload and "period_end" in payload


def test_build_facts_skips_blocked_titles(conn):
    seed_drop(conn, 10, "Fine Game", 2000, 1000)
    seed_drop(conn, 20, "Hentai Puzzle", 2000, 1000)
    with conn.cursor() as cur:
        payload = facts.build_facts(cur, days=7)
    assert [d["appid"] for d in payload["top_drops"]] == [10]
