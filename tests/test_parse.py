import json
import pathlib
import unittest

from steamprice.steam import parse_price

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
        self.assertIsNone(parse_price({"success": True, "data": []}))


if __name__ == "__main__":
    unittest.main()
