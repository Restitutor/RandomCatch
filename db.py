from collections.abc import Collection

import aiosqlite

from models import ItemKey, UserId


class Database:
    _conn: aiosqlite.Connection

    async def connect(self, path: str) -> None:
        self._conn = await aiosqlite.connect(path)
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventories (
                User INTEGER,
                Item TEXT,
                Quantity INTEGER,
                PRIMARY KEY (User, Item)
            )
            """,
        )
        await self._conn.commit()

    async def close(self) -> None:
        await self._conn.close()

    async def add_item(self, user: UserId, item: ItemKey, quantity: int = 1) -> None:
        await self._conn.execute(
            """
            INSERT INTO inventories (User, Item, Quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(User, Item) DO UPDATE SET Quantity = Quantity + excluded.Quantity
            """,
            (user, item, quantity),
        )
        await self._conn.commit()

    async def get_inventory(self, user: UserId) -> dict[ItemKey, int]:
        async with self._conn.execute(
            "SELECT Item, Quantity FROM inventories WHERE User = ?", (user,),
        ) as cursor:
            return {row[0]: row[1] async for row in cursor}

    async def get_leaderboard(self, limit: int = 10) -> dict[UserId, int]:
        async with self._conn.execute(
            "SELECT User, COUNT(DISTINCT Item) AS c FROM inventories "
            "GROUP BY User ORDER BY c DESC LIMIT ?",
            (limit,),
        ) as cursor:
            return {row[0]: row[1] async for row in cursor}

    async def prune_items(self, valid_keys: Collection[ItemKey]) -> int:
        keys = tuple(valid_keys)
        placeholders = ",".join(["?"] * len(keys))
        cursor = await self._conn.execute(
            f"DELETE FROM inventories WHERE Item NOT IN ({placeholders})", keys,
        )
        await self._conn.commit()
        return cursor.rowcount
