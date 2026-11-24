"""Exported CSVs must not carry cells a spreadsheet would run as formulas."""
import csv
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from utils.export import csv_safe  # noqa: E402


class CsvSafeTests(unittest.TestCase):
    def test_formula_like_text_is_neutralised(self):
        df = pd.DataFrame({
            "name": ['=HYPERLINK("https://evil.example","Slack")', "+1+1", "-2+3", "@SUM(A1)", "\t=1", "Slack"],
            "users": [3, 0, -5, 1, 2, 312],
            "scim_enabled": [True, False, True, False, True, False],
        })
        rows = list(csv.DictReader(io.StringIO(csv_safe(df).to_csv(index=False))))
        names = [row["name"] for row in rows]
        self.assertEqual(names[:5], ["'" + value for value in df["name"][:5]])
        self.assertEqual(names[5], "Slack")
        self.assertFalse(any(name[0] in "=+-@\t\r" for name in names))

    def test_numbers_booleans_and_the_original_frame_are_untouched(self):
        df = pd.DataFrame({"name": ["=1"], "users": [-5], "scim_enabled": [True]})
        safe = csv_safe(df)
        self.assertEqual(int(safe["users"][0]), -5)
        self.assertEqual(bool(safe["scim_enabled"][0]), True)
        self.assertEqual(df["name"][0], "=1")

    def test_sample_data_is_unchanged(self):
        from utils.mock_data import get_mock_apps

        df = pd.DataFrame(get_mock_apps())
        self.assertEqual(csv_safe(df).to_csv(index=False), df.to_csv(index=False))


if __name__ == "__main__":
    unittest.main()
