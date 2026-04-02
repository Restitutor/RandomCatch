import os
import sys
import tempfile
import types
import unittest

# Mock the config module before importing cogs.admin — config.py reads a token
# file at import time which doesn't exist in the test environment.
_mock_config = types.ModuleType("config")
_mock_config.ADMIN_IDS = {100, 200}
_mock_config.TOKEN = "fake"
_mock_config.DATABASE = ":memory:"
_mock_config.DATA_FILE = "data.csv"
_mock_config.RANDOM_DROP_CHANCE = 0.0
_mock_config.TOKEN_FILE = "token"
sys.modules.setdefault("config", _mock_config)

import pathlib

from cogs.admin import Permissions  # noqa: E402
from utils import save_json  # noqa: E402


class TestPermissions(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self._orig_dir = pathlib.Path.cwd()
        os.chdir(self.tmpdir)

    def tearDown(self) -> None:
        os.chdir(self._orig_dir)

    def _write_roles(self, data) -> None:
        save_json("roles.json", data)

    def test_owner_from_admin_ids(self) -> None:
        self._write_roles({"owners": [], "global_admins": []})
        p = Permissions()
        assert p.is_owner(100)

    def test_owner_from_roles_json(self) -> None:
        self._write_roles({"owners": [999], "global_admins": []})
        p = Permissions()
        assert p.is_owner(999)

    def test_global_admin(self) -> None:
        self._write_roles({"owners": [], "global_admins": [888]})
        p = Permissions()
        assert p.is_admin(888)
        assert not p.is_owner(888)

    def test_not_admin(self) -> None:
        self._write_roles({"owners": [], "global_admins": []})
        p = Permissions()
        assert not p.is_admin(777, member=None)

    def test_reload(self) -> None:
        self._write_roles({"owners": [], "global_admins": []})
        p = Permissions()
        assert not p.is_owner(999)
        self._write_roles({"owners": [999], "global_admins": []})
        p.reload()
        assert p.is_owner(999)


if __name__ == "__main__":
    unittest.main()
