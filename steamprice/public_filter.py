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
    "sex",
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

# strip numbered dlc / pass spam so "Foo - Expansion Pass 47" collapses with
# its siblings. kept intentionally greedy on trailing junk, not on core titles.
_FAMILY_TRAILING = re.compile(
    r"""(?ix)
    (?:
      [\s:.\-]+
      (?:
        expansion\s*pass | season\s*pass | soundtrack | ost |
        deluxe\s*edition | ultimate\s*edition | definitive\s*edition |
        game\s*of\s*the\s*year(?:\s*edition)? | goty(?:\s*edition)? |
        dlc | pack | bundle | content | episode | chapter | volume | vol
      )?
      [\s:.\-]*
      \d*
    )+$
    """
)


def is_blocked_name(name: str | None) -> bool:
    if not name:
        return False
    return _PATTERN.search(name) is not None


def sql_exclude_name(column: str) -> str:
    # postgres regex, case insensitive
    terms = "|".join(re.escape(t) for t in BLOCKED)
    return f"NOT (lower({column}) ~* '{terms}')"


def title_family(name: str | None) -> str:
    if not name:
        return ""
    s = " ".join(name.lower().split())
    while True:
        nxt = _FAMILY_TRAILING.sub("", s).rstrip(" :.-")
        nxt = re.sub(r"\s+\d+$", "", nxt)
        if nxt == s:
            break
        s = nxt
    return s or name.lower()


def diversify_drops(by_savings, by_percent, target, max_per_family=1):
    """Interleave savings / percent rankings, cap near-duplicate title families."""
    balanced = []
    seen = set()
    family_counts = {}
    positions = [0, 0]
    groups = [by_savings, by_percent]
    while len(balanced) < target:
        preferred = len(balanced) % 2
        picked = None
        for group_index in (preferred, 1 - preferred):
            group = groups[group_index]
            while positions[group_index] < len(group):
                row = group[positions[group_index]]
                positions[group_index] += 1
                if row["appid"] in seen:
                    continue
                family = title_family(row.get("name"))
                if family_counts.get(family, 0) >= max_per_family:
                    continue
                picked = row
                break
            if picked is not None:
                break
        if picked is None:
            break
        seen.add(picked["appid"])
        family = title_family(picked.get("name"))
        family_counts[family] = family_counts.get(family, 0) + 1
        balanced.append(picked)
    return balanced
