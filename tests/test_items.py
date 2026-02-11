import csv
import os
import tempfile
import unittest

from items import load_items


class TestLoadItems(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _write_csv(self, header, rows):
        path = os.path.join(self.tmpdir, "test.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for row in rows:
                writer.writerow(row)
        return path

    def test_load_basic(self):
        path = self._write_csv(
            ["key", "category", "en", "fr"],
            [
                ["a", "functions", "alpha", "alpha_fr"],
                ["b", "functions", "beta", "beta_fr"],
                ["c", "sets", "gamma", "gamma_fr"],
            ],
        )
        items = load_items(path)
        self.assertEqual(len(items), 3)
        self.assertEqual(items["a"].names["en"], "alpha")
        self.assertEqual(items["b"].category, "functions")
        self.assertEqual(items["c"].names["fr"], "gamma_fr")

    def test_missing_lang_skipped(self):
        path = self._write_csv(
            ["key", "category", "en", "fr"],
            [["a", "functions", "alpha", ""]],
        )
        items = load_items(path)
        self.assertIn("en", items["a"].names)
        self.assertNotIn("fr", items["a"].names)

    def test_auto_discovers_languages(self):
        path = self._write_csv(
            ["key", "category", "en", "fr", "de"],
            [["a", "constants", "alpha", "alpha_fr", "alpha_de"]],
        )
        items = load_items(path)
        self.assertEqual(set(items["a"].names.keys()), {"en", "fr", "de"})

    def test_invalid_category_rejected(self):
        path = self._write_csv(
            ["key", "category", "en"],
            [["a", "bogus", "alpha"]],
        )
        with self.assertRaises(ValueError):
            load_items(path)


if __name__ == "__main__":
    unittest.main()
