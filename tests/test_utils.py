import os
import tempfile
import unittest

from utils import load_json, save_json


class TestJsonPersistence(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "test.json")

    def test_roundtrip(self):
        data = {"items": [1, 2, 3], "name": "test"}
        save_json(self.path, data)
        loaded = load_json(self.path)
        self.assertEqual(loaded, data)

    def test_load_missing(self):
        result = load_json(os.path.join(self.tmpdir, "nope.json"))
        self.assertEqual(result, {})

    def test_load_invalid_json(self):
        with open(self.path, "w") as f:
            f.write("not json {{{")
        result = load_json(self.path)
        self.assertEqual(result, {})

    def test_save_overwrites(self):
        save_json(self.path, {"a": 1})
        save_json(self.path, {"b": 2})
        self.assertEqual(load_json(self.path), {"b": 2})

    def test_unicode(self):
        data = {"key": "π"}
        save_json(self.path, data)
        self.assertEqual(load_json(self.path), data)


if __name__ == "__main__":
    unittest.main()
