#!/usr/bin/env python3
"""
Database operations for the Discord math catch bot.
Handles inventory management and database interactions.
"""

from typing import Dict, Tuple

import aiosqlite
from config import DATABASE
from utils import logger
from pathlib import Path
from rapidfuzz import process

DATA_CSV = Path(__file__).resolve().parent / "data.csv"

category_length: dict[str, int] = {
    'numbers1-50': 50,
    'numbers51-100': 51,
    'sets': 20,
    'constants': 55,
    'functions': 94,
    'theorems': 7,
    'symbols': 56,
    'capitalgreek': 24,
    'smallgreek': 31,
    'sequence': 4
}


def categorize_objects_from_csv() -> dict[str, set[str]]:
    """
    Read `data.csv` and create a mapping from category name to a set of objects (2nd column)
    using the counts provided in `category_length`.

    Behavior:
    - Reads lines in order. For each category in `category_length` (in insertion order),
      it will take the next N objects from the 2nd column where N is the category's length.
    - If there are fewer remaining objects than requested, it takes what's available.
    - Returns a dict mapping category name -> set(objects).
    """
    # Read all lines and extract second column values
    text = DATA_CSV.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    objects = []  # 0-based sequential list of 2nd-column values
    for ln in lines:
        parts = ln.split(",")
        if len(parts) >= 2:
            objects.append(parts[0])
        else:
            objects.append("")

    result: dict[str, set[str]] = {}
    idx = 0  # current index into objects list (0-based)
    for cat, length in category_length.items():
        take = objects[idx: idx + length]
        result[cat] = set(take)
        idx += length
        if idx >= len(objects):
            # no more objects to assign; remaining categories get empty sets
            break

    # ensure all categories exist in result (empty set if none assigned)
    for cat in category_length.keys():
        result.setdefault(cat, set())

    return result
categories = categorize_objects_from_csv()
async def create_table() -> None:
    """
    Creates the inventories table if it doesn't exist.
    """
    try:
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
        logger.info(f"Successfully created/verified inventories table in {DATABASE}")
    except Exception as e:
        logger.error(f"Error creating database table: {e}")
        raise


async def add_item(user: int, item: str, quantity: int) -> None:
    """
    Adds an item to a user's inventory or increases its quantity if it already exists.

    Args:
        user: User ID
        item: Item ID
        quantity: Quantity to add
    """
    try:
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
        logger.info(f"Added {quantity} of item '{item}' to user {user}")
    except Exception as e:
        logger.error(f"Error adding item to inventory: {e}")
        raise


async def list_items(user: int, category: str= 'all') -> Dict[str, int]:
    """
    Lists all items in a user's inventory.

    Args:
        user: User ID

    Returns:
        Dictionary mapping item IDs to quantities
    """
    category = process.extractOne(category.lower(), category_length.keys())[0] if category != "all" else "all"
    try:
        async with aiosqlite.connect(DATABASE) as db:
            async with db.execute(
                "SELECT Item, Quantity FROM inventories WHERE User = ?",
                (user,),
            ) as cursor:
                rows = await cursor.fetchall()
                if category == 'all':
                    result = {row[0]: row[1] for row in rows}
                else:
                    valid_items = categories.get(category, set())
                    result = {row[0]: row[1] for row in rows if row[0] in valid_items}
        logger.info(f"Retrieved {len(result)} items for user {user}")
        return result
    except Exception as e:
        logger.error(f"Error listing items from inventory: {e}")
        raise


async def leaderboard(limit: int = 10) -> dict[str, int]:
    """Lists top 10 by xp.

    Returns:
        Dictionary mapping user IDs to quantities

    """
    try:
        async with (
            aiosqlite.connect(DATABASE) as db,
            db.execute(
                "SELECT User, count(distinct Item) as c FROM inventories group by User order by c desc limit ?",
                (limit,),
            ) as cursor,
        ):
            rows = await cursor.fetchall()
            result = {row[0]: row[1] for row in rows}
        logger.info(f"Retrieved {len(result)} results.")
        return result
    except Exception as e:
        logger.error(f"Error listing items from inventory: {e}")
        raise


async def prune_item(catchables: Tuple[str, ...]) -> None:
    """
    Removes items from the database that are not in the catchables list.

    Args:
        catchables: Tuple of valid catchable item IDs
    """
    try:
        # Fix SQL injection by using proper parameterization
        placeholders = ",".join(["?"] * len(catchables))
        sql = f"DELETE FROM inventories WHERE Item NOT IN ({placeholders})"

        async with aiosqlite.connect(DATABASE) as db:
            cursor = await db.execute(sql, catchables)
            deleted_count = cursor.rowcount
            await db.commit()

        logger.info(f"Pruned {deleted_count} invalid items from inventory database")
    except Exception as e:
        logger.error(f"Error pruning items from inventory: {e}")
        raise
