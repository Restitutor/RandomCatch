#!/usr/bin/env python3
"""
Game mechanics for the Discord math catch bot.
Handles the core game logic including catching and dropping items.
"""

import asyncio
import random
import time
from typing import Dict, Tuple, Optional

from config import DATA_FILE, ADMIN_IDS
import db
from utils import logger, read_csv


class GameState:
    """
    Encapsulates game state and mechanics.
    """

    def __init__(self):
        self.catchables: Dict[str, Tuple[str, ...]] = {}
        self.last_catchable: Dict[int, str] = {}
        self.last_summon: Dict[int, int] = {}

    def initialize(self, filepath: str = DATA_FILE) -> None:
        """
        Initializes the game state by loading catchables.

        Args:
            filepath: Path to the CSV file with catchables
        """
        self.catchables = load_catchables(filepath)
        logger.info(f"Loaded {len(self.catchables)} catchable items")

    def can_summon(self, user_id: int) -> bool:
        """
        Checks if a user can summon a catchable item.

        Args:
            user_id: Discord user ID

        Returns:
            True if the user can summon, False otherwise
        """
        if user_id in ADMIN_IDS:
            return True

        HOUR = 3600
        if self.last_summon.get(user_id, 0) < time.time() - HOUR:
            self.last_summon[user_id] = round(time.time())
            return True

        return False

    def get_summon_cooldown(self, user_id: int) -> int:
        """
        Gets the remaining cooldown time for a user's summon ability.

        Args:
            user_id: Discord user ID

        Returns:
            Seconds remaining until the user can summon again
        """
        if user_id not in self.last_summon:
            return 0

        return max(0, round(self.last_summon[user_id] + 3600 - time.time()))

    async def summon(self, channel_id: int, user_id: int = None) -> Tuple[str, str]:
        """
        Summons a catchable item in a channel.

        Args:
            channel_id: Discord channel ID
            user_id: Optional user ID for weighted selection

        Returns:
            Tuple of (message, key)
        """
        msg, key = await drop(channel_id, self.catchables, user_id)
        self.last_catchable[channel_id] = key
        return msg, key

    def try_catch_in_channel(
        self, channel_id: int, text: str
    ) -> Tuple[Optional[str], bool]:
        """
        Attempts to catch an item in a channel based on the message text.

        Args:
            channel_id: Discord channel ID
            text: Message text

        Returns:
            Tuple of (message, caught)
        """
        if channel_id not in self.last_catchable:
            return None, False

        key = self.last_catchable[channel_id]
        out, caught = try_catch(key, self.catchables[key], text)

        if caught:
            del self.last_catchable[channel_id]

        return out, caught

    async def list_inventory(self, user_id: int) -> str:
        """
        Lists items in a user's inventory.

        Args:
            user_id: User ID

        Returns:
            Message containing inventory
        """
        return await list_inventory(user_id, self.catchables)

    async def list_completion(self, user_id: int) -> str:
        """
        Calculates and returns the user's completion percentage.

        Args:
            user_id: User ID

        Returns:
            Message containing completion percentage
        """
        return await list_completion(user_id, self.catchables)

    async def list_remaining(self, user_id: int) -> str:
        """
        Lists catchable items the user hasn't caught yet.

        Args:
            user_id: User ID

        Returns:
            Message containing remaining items
        """
        return await list_remaining(user_id, self.catchables)

    async def random_drop_task(self, channel_getter, allowed_channels, interval: int):
        """
        Task that periodically drops random items in allowed channels.

        Args:
            channel_getter: Function to fetch a channel by ID
            allowed_channels: List of allowed channel IDs
            interval: Time interval between drops in seconds
        """
        logger.info("Starting random drop task")

        while True:
            try:
                if allowed_channels:
                    channel_id = random.choice(allowed_channels)
                    channel = await channel_getter(channel_id)

                    msg, key = await self.summon(channel_id)

                    await channel.send(msg)
                    logger.info(f"Random drop in channel {channel_id}: {key}")

                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Error in random drop task: {e}")
                await asyncio.sleep(60)  # Wait a bit before retrying


def load_catchables(filepath: str = DATA_FILE) -> Dict[str, Tuple[str, ...]]:
    """
    Loads catchable items from a CSV file.

    Args:
        filepath: Path to the CSV file

    Returns:
        Dictionary mapping item IDs to tuples of aliases
    """
    try:
        return read_csv(filepath)
    except Exception as e:
        logger.error(f"Failed to load catchables: {e}")
        raise


def try_catch(
    key: str, aliases: Tuple[str, ...], text: str
) -> Tuple[Optional[str], bool]:
    """
    Checks if the given text includes one of the aliases for the catchable item.

    Args:
        key: The item ID
        aliases: Tuple of aliases for the item
        text: Text to check for aliases

    Returns:
        Tuple of (message, caught)
    """
    out = None

    for alias in aliases:
        if alias in text:
            out = f"Caught {key} -> {alias}"
            logger.info(f"User caught {key} with alias '{alias}'")
            return out, True

    if "catch" in text:
        out = "That is not the right name.."
        logger.debug(f"Failed catch attempt for {key}")

    return out, False


async def drop(
    channel_id: int, catchables: Dict[str, Tuple[str, ...]], user_id: int = None
) -> Tuple[str, str]:
    """
    Drops a catchable item in the channel, with higher probability for items
    not in the user's inventory when a user_id is provided.

    Args:
        channel_id: Discord channel ID
        catchables: Dictionary of catchable items
        user_id: Optional user ID to consider inventory for weighted selection

    Returns:
        Tuple of (message, key)
    """
    if not catchables:
        logger.error("No catchables available for dropping")
        return "Error: No catchables available!", ""

    # If no user_id provided or can't get inventory, fall back to random selection
    if user_id is None:
        key = random.choice(list(catchables.keys()))
    else:
        try:
            # Get user's current inventory
            inventory = await db.list_items(user_id)

            # Split items into two lists: new items and duplicates
            new_items = [item for item in catchables.keys() if item not in inventory]
            duplicate_items = [item for item in catchables.keys() if item in inventory]

            # Handle edge cases
            if not new_items:
                # No new items available, choose from duplicates
                key = random.choice(list(catchables.keys()))
                logger.info(
                    f"No new items available, dropped '{key}' for user {user_id}"
                )
            elif not duplicate_items:
                # No duplicates (new user), always drop a new item
                key = random.choice(new_items)
                logger.info(f"New user, dropped new item '{key}' for user {user_id}")
            else:
                # Calculate probability based on % of items that are new with minimum 20% chance
                probability = max(len(new_items) / len(catchables), 0.2)

                # Weighted selection based on calculated probability
                if random.random() < probability:
                    key = random.choice(new_items)
                    logger.info(
                        f"Dropped new item '{key}' for user {user_id} (prob: {probability:.2f})"
                    )
                else:
                    key = random.choice(duplicate_items)
                    logger.info(
                        f"Dropped duplicate item '{key}' for user {user_id} (prob: {probability:.2f})"
                    )
        except Exception as e:
            # On any error, fall back to completely random selection
            logger.error(
                f"Error in weighted item selection: {e}, falling back to random"
            )
            key = random.choice(list(catchables.keys()))

    logger.info(f"Dropped '{key}' in channel {channel_id}")
    return f"A new Math object dropped! `{key}`. Catch it by saying its name!", key


async def list_remaining(user: int, catchables: Dict[str, Tuple[str, ...]]) -> str:
    """
    Lists catchable items the user hasn't caught yet.

    Args:
        user: User ID
        catchables: Dictionary of all catchable items

    Returns:
        Message containing remaining items
    """
    try:
        inv = await db.list_items(user)
        items = sorted(set(catchables) - set(inv))
        if items:
            out = "Remaining\n`" + ", ".join(items) + "`"
            return out[:1999]  # Discord message limit
        else:
            return "You caught everything!"
    except Exception as e:
        logger.error(f"Error listing remaining items: {e}")
        return f"Error retrieving remaining items: {str(e)}"


async def list_inventory(user: int, catchables: Dict[str, Tuple[str, ...]]) -> str:
    """
    Lists items in a user's inventory.

    Args:
        user: User ID
        catchables: Dictionary of all catchable items

    Returns:
        Message containing inventory
    """
    try:
        items = await db.list_items(user)
        if items:
            out = "Inventory\n"
            for k, names in catchables.items():
                if k not in items:
                    continue

                try:
                    name = names[0]
                    out += f"{k} -> **{name}**: {items[k]}\n"
                except Exception as e:
                    logger.error(f"Error formatting inventory item {k}: {e}")

            return out[:1999]  # Discord message limit
        else:
            return "Inventory is empty! Catch more math objects!"
    except Exception as e:
        logger.error(f"Error listing inventory: {e}")
        return f"Error retrieving inventory: {str(e)}"


async def list_completion(user: int, catchables: Dict[str, Tuple[str, ...]]) -> str:
    """
    Calculates and returns the user's completion percentage.

    Args:
        user: User ID
        catchables: Dictionary of all catchable items

    Returns:
        Message containing completion percentage
    """
    try:
        logger.info(f"Calculating completion for user {user}")
        items = await db.list_items(user)
        count = len(items)
        return f"They have {count} items, so their MathDex progression is {round(count*100/len(catchables), 2)}%"
    except Exception as e:
        logger.error(f"Error calculating completion: {e}")
        return f"Error calculating completion: {str(e)}"
