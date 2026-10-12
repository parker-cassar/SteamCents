import pytest

from steamprice.public_filter import diversify_drops, is_blocked_name, title_family


@pytest.mark.parametrize("name", [
    "Hentai Puzzle",
    "My Porn Game",
    "XXX Simulator",
    "Totally Lewd Quest",
    "NSFW Dating",
    "Cybersex Chronicles [18+]",
    "Desktop Sex Doll",
])
def test_blocked_titles(name):
    assert is_blocked_name(name)


@pytest.mark.parametrize("name", [
    "Counter-Strike 2",
    "Hollow Knight",
    "Corn Quest",
    "Thing",
])
def test_clean_titles(name):
    assert not is_blocked_name(name)


@pytest.mark.parametrize("name,family", [
    ("Cyberphobia: Prologue - Expansion Pass 47", "cyberphobia: prologue"),
    ("Cyberphobia: Prologue - Expansion Pass 36", "cyberphobia: prologue"),
    ("Foo DLC 3", "foo"),
    ("Hollow Knight", "hollow knight"),
    ("Counter-Strike 2", "counter-strike"),
])
def test_title_family(name, family):
    assert title_family(name) == family


def test_diversify_drops_caps_one_per_family():
    clones = [
        {"appid": i, "name": f"Spam Pack {i}", "drop_cents": 100, "drop_pct": 99}
        for i in range(1, 6)
    ]
    other = {"appid": 99, "name": "Other Game", "drop_cents": 50, "drop_pct": 50}
    by_pct = clones + [other]
    by_sav = [other] + clones
    out = diversify_drops(by_sav, by_pct, target=3)
    assert len(out) == 2
    assert {r["appid"] for r in out} == {1, 99}
