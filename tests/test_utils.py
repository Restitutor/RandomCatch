import os
import pathlib
import tempfile
import unittest

from utils import load_json, save_json


class TestJsonPersistence(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "test.json")

    def test_roundtrip(self) -> None:
        data = {"items": [1, 2, 3], "name": "test"}
        save_json(self.path, data)
        loaded = load_json(self.path)
        assert loaded == data

    def test_load_missing(self) -> None:
        result = load_json(os.path.join(self.tmpdir, "nope.json"))
        assert result == {}

    def test_load_invalid_json(self) -> None:
        with pathlib.Path(self.path).open("w") as f:
            f.write("not json {{{")
        result = load_json(self.path)
        assert result == {}

    def test_save_overwrites(self) -> None:
        save_json(self.path, {"a": 1})
        save_json(self.path, {"b": 2})
        assert load_json(self.path) == {"b": 2}

    def test_unicode(self) -> None:
        data = {"key": "π"}
        save_json(self.path, data)
        assert load_json(self.path) == data


if __name__ == "__main__":
    unittest.main()
