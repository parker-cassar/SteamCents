from datetime import timedelta

from steamprice import config

HOT = 0     # moved price lately, worth watching
NORMAL = 1  # priced and quiet
SLOW = 2    # free, unpriced, or steam keeps not answering


def classify(priced, last_changed_at, now, failures=0):
    if failures >= config.MAX_FAILURES:
        return SLOW
    if not priced:
        return SLOW
    if last_changed_at is None:
        return NORMAL
    if now - last_changed_at <= timedelta(days=config.CHANGED_RECENTLY_DAYS):
        return HOT
    return NORMAL


def next_due(tier, now):
    return now + timedelta(hours=config.TIER_HOURS[tier])
