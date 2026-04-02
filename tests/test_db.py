import unittest

from db import Database


class TestDatabase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = Database()
        await self.db.connect(":memory:")

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_add_and_get(self) -> None:
        await self.db.add_item(1, "cos")
        inv = await self.db.get_inventory(1)
        assert inv == {"cos": 1}

    async def test_upsert_increments(self) -> None:
        await self.db.add_item(1, "cos")
        await self.db.add_item(1, "cos")
        inv = await self.db.get_inventory(1)
        assert inv["cos"] == 2

    async def test_empty_inventory(self) -> None:
        inv = await self.db.get_inventory(999)
        assert inv == {}

    async def test_leaderboard_ordering(self) -> None:
        await self.db.add_item(1, "a")
        await self.db.add_item(2, "a")
        await self.db.add_item(2, "b")
        await self.db.add_item(3, "a")
        await self.db.add_item(3, "b")
        await self.db.add_item(3, "c")
        lb = await self.db.get_leaderboard()
        users = list(lb.keys())
        assert users == [3, 2, 1]

    async def test_leaderboard_empty(self) -> None:
        lb = await self.db.get_leaderboard()
        assert lb == {}

    async def test_leaderboard_limit(self) -> None:
        for i in range(15):
            await self.db.add_item(i, f"item_{i}")
        lb = await self.db.get_leaderboard(limit=10)
        assert len(lb) == 10

    async def test_prune_removes_stale(self) -> None:
        await self.db.add_item(1, "valid")
        await self.db.add_item(1, "stale")
        await self.db.prune_items(["valid"])
        inv = await self.db.get_inventory(1)
        assert "valid" in inv
        assert "stale" not in inv

    async def test_prune_returns_count(self) -> None:
        await self.db.add_item(1, "a")
        await self.db.add_item(1, "b")
        await self.db.add_item(1, "c")
        count = await self.db.prune_items(["a"])
        assert count == 2


if __name__ == "__main__":
    unittest.main()
