import csv
import os
import pathlib
import tempfile
import unittest

import pytest

from items import load_items


class TestLoadItems(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()

    def _write_csv(self, header, rows):
        path = os.path.join(self.tmpdir, "test.csv")
        with pathlib.Path(path).open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for row in rows:
                writer.writerow(row)
        return path

    def test_load_basic(self) -> None:
        path = self._write_csv(
            ["key", "category", "en", "fr"],
            [
                ["a", "functions", "alpha", "alpha_fr"],
                ["b", "functions", "beta", "beta_fr"],
                ["c", "sets", "gamma", "gamma_fr"],
            ],
        )
        items = load_items(path)
        assert len(items) == 3
        assert items["a"].names["en"] == "alpha"
        assert items["b"].category == "functions"
        assert items["c"].names["fr"] == "gamma_fr"

    def test_missing_lang_skipped(self) -> None:
        path = self._write_csv(
            ["key", "category", "en", "fr"],
            [["a", "functions", "alpha", ""]],
        )
        items = load_items(path)
        assert "en" in items["a"].names
        assert "fr" not in items["a"].names

    def test_auto_discovers_languages(self) -> None:
        path = self._write_csv(
            ["key", "category", "en", "fr", "de"],
            [["a", "constants", "alpha", "alpha_fr", "alpha_de"]],
        )
        items = load_items(path)
        assert set(items["a"].names.keys()) == {"en", "fr", "de"}

    def test_invalid_category_rejected(self) -> None:
        path = self._write_csv(
            ["key", "category", "en"],
            [["a", "bogus", "alpha"]],
        )
        with pytest.raises(ValueError):
            load_items(path)


if __name__ == "__main__":
    unittest.main()
