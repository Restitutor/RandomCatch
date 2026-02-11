import unittest

from db import Database


class TestDatabase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = Database()
        await self.db.connect(":memory:")

    async def asyncTearDown(self):
        await self.db.close()

    async def test_add_and_get(self):
        await self.db.add_item(1, "cos")
        inv = await self.db.get_inventory(1)
        self.assertEqual(inv, {"cos": 1})

    async def test_upsert_increments(self):
        await self.db.add_item(1, "cos")
        await self.db.add_item(1, "cos")
        inv = await self.db.get_inventory(1)
        self.assertEqual(inv["cos"], 2)

    async def test_empty_inventory(self):
        inv = await self.db.get_inventory(999)
        self.assertEqual(inv, {})

    async def test_leaderboard_ordering(self):
        await self.db.add_item(1, "a")
        await self.db.add_item(2, "a")
        await self.db.add_item(2, "b")
        await self.db.add_item(3, "a")
        await self.db.add_item(3, "b")
        await self.db.add_item(3, "c")
        lb = await self.db.get_leaderboard()
        users = list(lb.keys())
        self.assertEqual(users, [3, 2, 1])

    async def test_leaderboard_empty(self):
        lb = await self.db.get_leaderboard()
        self.assertEqual(lb, {})

    async def test_leaderboard_limit(self):
        for i in range(15):
            await self.db.add_item(i, f"item_{i}")
        lb = await self.db.get_leaderboard(limit=10)
        self.assertEqual(len(lb), 10)

    async def test_prune_removes_stale(self):
        await self.db.add_item(1, "valid")
        await self.db.add_item(1, "stale")
        await self.db.prune_items(["valid"])
        inv = await self.db.get_inventory(1)
        self.assertIn("valid", inv)
        self.assertNotIn("stale", inv)

    async def test_prune_returns_count(self):
        await self.db.add_item(1, "a")
        await self.db.add_item(1, "b")
        await self.db.add_item(1, "c")
        count = await self.db.prune_items(["a"])
        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
