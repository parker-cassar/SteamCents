from datetime import timedelta

import pytest

from steamprice import config, schedule, sweep


def priced(cents, discount=0, initial=None):
    return {
        "success": True,
        "data": {
            "price_overview": {
                "currency": "USD",
                "initial": initial if initial is not None else cents,
                "final": cents,
                "discount_percent": discount,
            }
        },
    }


UNPRICED = {"success": True, "data": []}
NO_STORE_PAGE = {"success": False}


@pytest.fixture
def steam(monkeypatch):
    reply = {}

    def serve(ids, cc=None):
        return {str(i): reply[i] for i in ids if i in reply}

    monkeypatch.setattr(sweep, "fetch_appdetails", serve)
    return reply


def rows(conn, appid):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT final_cents FROM price_observations WHERE appid = %s ORDER BY observed_at",
            (appid,),
        )
        return [r[0] for r in cur.fetchall()]


def app_row(conn, appid, *cols):
    with conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(cols)} FROM apps WHERE appid = %s", (appid,))
        return cur.fetchone()


def test_same_price_twice_writes_one_row(conn, apps, steam):
    ids = apps(10)
    steam[10] = priced(1999)

    sweep.process_batch(conn, ids)
    first = app_row(conn, 10, "last_checked_at")[0]
    sweep.process_batch(conn, ids)

    assert rows(conn, 10) == [1999]
    # stamped either way, which is what keeps it from jamming the queue
    assert app_row(conn, 10, "last_checked_at")[0] > first


def test_changed_price_writes_a_second_row(conn, apps, steam):
    ids = apps(10)
    steam[10] = priced(1999)
    sweep.process_batch(conn, ids)
    steam[10] = priced(999, discount=50, initial=1999)
    sweep.process_batch(conn, ids)

    assert rows(conn, 10) == [1999, 999]
    assert app_row(conn, 10, "last_changed_at")[0] is not None


def test_first_look_is_not_a_change(conn, apps, steam):
    ids = apps(10)
    steam[10] = priced(1999)
    sweep.process_batch(conn, ids)

    assert rows(conn, 10) == [1999]
    assert app_row(conn, 10, "last_changed_at")[0] is None


def test_discount_alone_counts_as_a_change(conn, apps, steam):
    ids = apps(10)
    steam[10] = priced(1000, discount=0, initial=1000)
    sweep.process_batch(conn, ids)
    steam[10] = priced(1000, discount=50, initial=2000)
    sweep.process_batch(conn, ids)

    assert len(rows(conn, 10)) == 2


def test_unpriced_is_an_answer_not_a_failure(conn, apps, steam):
    ids = apps(10)
    steam[10] = UNPRICED

    for _ in range(6):
        sweep.process_batch(conn, ids)

    seen, failures, tier = app_row(conn, 10, "no_price_seen_at", "consecutive_failures", "tier")
    assert seen is not None
    assert failures == 0
    assert tier == schedule.SLOW
    assert rows(conn, 10) == []


def test_missing_appid_parks_after_max_failures(conn, apps, steam):
    ids = apps(10)
    # steam serves nothing at all for it
    for n in range(1, config.MAX_FAILURES + 3):
        sweep.process_batch(conn, ids)
        expected = min(n, config.MAX_FAILURES)
        assert app_row(conn, 10, "consecutive_failures")[0] == expected

    assert app_row(conn, 10, "tier")[0] == schedule.SLOW


def test_no_store_page_counts_as_a_failure(conn, apps, steam):
    ids = apps(10)
    steam[10] = NO_STORE_PAGE
    sweep.process_batch(conn, ids)

    failures, seen = app_row(conn, 10, "consecutive_failures", "no_price_seen_at")
    assert failures == 1
    assert seen is None


def test_a_good_answer_clears_the_counter(conn, apps, steam):
    ids = apps(10)
    sweep.process_batch(conn, ids)
    sweep.process_batch(conn, ids)
    assert app_row(conn, 10, "consecutive_failures")[0] == 2

    steam[10] = priced(500)
    sweep.process_batch(conn, ids)
    assert app_row(conn, 10, "consecutive_failures")[0] == 0


def test_claim_skips_apps_that_are_not_due(conn, apps, steam):
    apps(10, 20)
    steam[10] = priced(1999)
    steam[20] = priced(2999)

    with conn.cursor() as cur:
        assert sorted(sweep.claim(cur, 10)) == [10, 20]

    sweep.process_batch(conn, [10, 20])

    with conn.cursor() as cur:
        assert sweep.claim(cur, 10) == []


def test_claim_puts_never_checked_apps_first(conn, apps, steam):
    apps(10, 20, 30)
    with conn.cursor() as cur:
        cur.execute("UPDATE apps SET next_due_at = now() - interval '1 hour' WHERE appid IN (10, 20)")
    conn.commit()

    with conn.cursor() as cur:
        # 30 is still at epoch, so it outranks the two that were checked an hour ago
        assert sweep.claim(cur, 3)[0] == 30


def test_parked_app_still_comes_back_round_eventually(conn, apps, steam):
    ids = apps(10)
    for _ in range(config.MAX_FAILURES):
        sweep.process_batch(conn, ids)

    due = app_row(conn, 10, "next_due_at")[0]
    with conn.cursor() as cur:
        cur.execute("SELECT now()")
        now = cur.fetchone()[0]

    # parked, but scheduled rather than dropped on the floor. next_due_at comes
    # off the python clock a hair before postgres reads now(), so allow slack.
    slow = timedelta(hours=config.TIER_HOURS[schedule.SLOW])
    assert due > now
    assert due - now <= slow + timedelta(minutes=1)
    assert due - now > slow - timedelta(minutes=1)
    with conn.cursor() as cur:
        cur.execute("UPDATE apps SET next_due_at = now() - interval '1 second'")
    conn.commit()
    with conn.cursor() as cur:
        assert sweep.claim(cur, 5) == [10]


def test_delisted_apps_are_never_claimed(conn, apps, steam):
    apps(10)
    with conn.cursor() as cur:
        cur.execute("UPDATE apps SET delisted_at = now() WHERE appid = 10")
    conn.commit()
    with conn.cursor() as cur:
        assert sweep.claim(cur, 5) == []
