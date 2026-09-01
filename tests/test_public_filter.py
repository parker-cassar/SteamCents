import pytest

from steamprice.public_filter import is_blocked_name


@pytest.mark.parametrize("name", [
    "Hentai Puzzle",
    "My Porn Game",
    "XXX Simulator",
    "Totally Lewd Quest",
    "NSFW Dating",
])
def test_blocked_titles(name):
    assert is_blocked_name(name)


@pytest.mark.parametrize("name", [
    "Counter-Strike 2",
    "Hollow Knight",
    "Essex",
    "Corn Quest",
    "Thing",
])
def test_clean_titles(name):
    assert not is_blocked_name(name)
