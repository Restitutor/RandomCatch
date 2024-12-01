import asyncio

import aiosqlite

DATABASE = "inventory.db"


async def create_table() -> None:
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS inventories (
                User INTEGER,
                Item TEXT,
                Quantity INTEGER,
                PRIMARY KEY (User, Item)
            )
        """
        )
        await db.commit()


async def add_item(user: int, item: str, quantity: int) -> None:
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute(
            """
            INSERT INTO inventories (User, Item, Quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(User, Item) DO UPDATE SET Quantity = Quantity + excluded.Quantity
            """,
            (user, item, quantity),
        )
        await db.commit()


async def list_items(user: int) -> dict[str, int]:
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute(
            "SELECT Item, Quantity FROM inventories WHERE User = ?",
            (user,),
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}


async def prune_item(catchables: list[str]) -> None:
    # Not safe
    sql = f"delete from inventories where Item not in {catchables}"
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute(sql)
        await db.commit()
