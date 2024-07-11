import asyncio

import aiosqlite

DATABASE = "inventory.db"


async def create_table() -> None:
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventories (
                User INTEGER,
                Item TEXT,
                Quantity INTEGER,
                PRIMARY KEY (User, Item)
            )
        """)
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
            "SELECT Item, Quantity FROM inventories WHERE User = ?", (user,),
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}


async def main() -> None:
    await create_table()
    await add_item(1, "Widget", 10)
    await add_item(1, "Gadget", 5)
    items = await list_items(1)
    print(f"User 1's Inventory: {items}")


# Run the main function as the entry point
if __name__ == "__main__":
    asyncio.run(main())
