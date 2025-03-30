#!/usr/bin/env python3
"""
Database operations for the Discord math catch bot.
Handles inventory management and database interactions.
"""

import asyncio
import logging
from typing import Dict, List, Tuple, Set, Any, Optional

import aiosqlite
from config import DATABASE
from utils import logger


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


async def list_items(user: int) -> Dict[str, int]:
    """
    Lists all items in a user's inventory.

    Args:
        user: User ID

    Returns:
        Dictionary mapping item IDs to quantities
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            async with db.execute(
                "SELECT Item, Quantity FROM inventories WHERE User = ?",
                (user,),
            ) as cursor:
                rows = await cursor.fetchall()
                result = {row[0]: row[1] for row in rows}
        logger.info(f"Retrieved {len(result)} items for user {user}")
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
