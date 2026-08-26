import unittest
from datetime import datetime, timedelta, timezone

from steamprice import config, schedule

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


class ClassifyTests(unittest.TestCase):
    def test_moved_lately_is_hot(self):
        self.assertEqual(schedule.classify(True, NOW - timedelta(days=2), NOW), schedule.HOT)

    def test_quiet_paid_app_is_normal(self):
        self.assertEqual(schedule.classify(True, NOW - timedelta(days=30), NOW), schedule.NORMAL)

    def test_never_changed_is_normal(self):
        self.assertEqual(schedule.classify(True, None, NOW), schedule.NORMAL)

    def test_unpriced_is_slow(self):
        self.assertEqual(schedule.classify(False, None, NOW), schedule.SLOW)

    def test_parked_is_slow_even_if_it_used_to_move(self):
        tier = schedule.classify(True, NOW, NOW, failures=config.MAX_FAILURES)
        self.assertEqual(tier, schedule.SLOW)

    def test_boundary_is_still_hot(self):
        edge = NOW - timedelta(days=config.CHANGED_RECENTLY_DAYS)
        self.assertEqual(schedule.classify(True, edge, NOW), schedule.HOT)
        self.assertEqual(
            schedule.classify(True, edge - timedelta(seconds=1), NOW), schedule.NORMAL
        )

    def test_due_times_come_from_config(self):
        for tier in (schedule.HOT, schedule.NORMAL, schedule.SLOW):
            self.assertEqual(
                schedule.next_due(tier, NOW),
                NOW + timedelta(hours=config.TIER_HOURS[tier]),
            )
        self.assertLess(schedule.next_due(schedule.HOT, NOW), schedule.next_due(schedule.SLOW, NOW))


if __name__ == "__main__":
    unittest.main()
