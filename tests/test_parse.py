import json
import pathlib
import unittest

from steamprice.steam import answered, parse_price

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "appdetails_batch_100.json"
EXPECTED = ROOT / "tests" / "fixtures" / "appdetails_batch_100.expected.json"


class ParsePriceTests(unittest.TestCase):
    def test_fixture_counts(self):
        batch = json.loads(FIXTURE.read_text())
        expected = json.loads(EXPECTED.read_text())
        priced = 0
        empty = 0
        for entry in batch.values():
            if parse_price(entry) is not None:
                priced += 1
            elif isinstance(entry.get("data"), list) and entry.get("data") == []:
                empty += 1
        self.assertEqual(len(batch), expected["returned"])
        self.assertEqual(priced, expected["priced"])
        self.assertEqual(empty, expected["empty_data"])

    def test_stardew_shape(self):
        entry = {
            "success": True,
            "data": {
                "price_overview": {
                    "currency": "USD",
                    "initial": 1499,
                    "final": 1499,
                    "discount_percent": 0,
                }
            },
        }
        self.assertEqual(parse_price(entry), {
            "currency": "USD",
            "initial_cents": 1499,
            "final_cents": 1499,
            "discount_pct": 0,
        })

    def test_empty_data(self):
        entry = {"success": True, "data": []}
        self.assertIsNone(parse_price(entry))
        self.assertTrue(answered(entry))

    def test_success_false_is_not_an_answer(self):
        self.assertFalse(answered({"success": False}))
        self.assertFalse(answered(None))

    def test_fixture_unpriced_all_answered(self):
        batch = json.loads(FIXTURE.read_text())
        expected = json.loads(EXPECTED.read_text())
        unpriced = [e for e in batch.values() if parse_price(e) is None and answered(e)]
        self.assertEqual(len(unpriced), expected["empty_data"])


if __name__ == "__main__":
    unittest.main()
