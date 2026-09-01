import re

# crude title blocklist for the public dashboard until we have mature flags
# from appdetails. substring match on lowercased names.
BLOCKED = (
    "hentai",
    "porn",
    "xxx",
    "nude",
    "nudity",
    "erotic",
    "lewd",
    "nsfw",
    "sex game",
    "adult game",
    "masturbat",
    "orgasm",
    "blowjob",
    "fap ",
    " fap",
    "boobs",
    "tits",
    "penis",
    "vagina",
    "strip club",
    "stripclub",
    "onlyfans",
)

_PATTERN = re.compile("|".join(re.escape(t) for t in BLOCKED), re.I)


def is_blocked_name(name: str | None) -> bool:
    if not name:
        return False
    return _PATTERN.search(name) is not None


def sql_exclude_name(column: str) -> str:
    # postgres regex, case insensitive
    terms = "|".join(re.escape(t) for t in BLOCKED)
    return f"NOT (lower({column}) ~* '{terms}')"
