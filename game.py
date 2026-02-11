#!/usr/bin/env python3
"""
Game mechanics for the Discord math catch bot.
Handles the core game logic including catching and dropping items.
"""

import asyncio
import random
import time
from utils import load_json, save_json
from typing import Dict, Literal, Tuple, Optional

from config import DATA_FILE, ADMIN_IDS, RANDOM_DROP_CHANCE
import db
from utils import logger, read_csv
from rapidfuzz import process

def find_closest_word(input_word: str, candidates: list[str], threshold: float = 75.0):
    if not candidates:
        return None
    match = process.extractOne(input_word, candidates)
    if match:
        best_word, score, _ = match
        if score >= threshold:
            return best_word
    return None


class GameState:
    """
    Encapsulates game state and mechanics.
    """

    def __init__(self):
        self.catchables: Dict[str, Tuple[str, ...]] = {}
        self.last_catchable: Dict[int, str] = {}
        self.last_summon: Dict[int, int] = {}
        # manage per-channel spawn worker tasks: cid (str) -> asyncio.Task
        self._spawn_tasks: Dict[str, asyncio.Task] = {}

    async def _spawn_worker(self, cid: str, channel_getter):
        """Worker that waits until the configured timer elapses, then attempts a spawn.

        This worker will loop: compute remaining time until next allowed spawn for the
        channel (based on `last_spawn` and configured timer), sleep until then, then
        apply the per-channel probability and summon if probability matches.
        It updates `spawn_rules.json` last_spawn timestamp after successful spawn.
        """
        try:
            while True:
                try:
                    rules = await asyncio.to_thread(load_json, "spawn_rules.json", {"guilds": {}, "last_spawn": {}})
                except Exception:
                    rules = {"guilds": {}, "last_spawn": {}}

                guilds = rules.get("guilds", {})
                # find the guild_rules that owns this channel or default
                guild_rules = None
                for gid, gdata in guilds.items():
                    if cid in gdata.get("timers", {}) or cid in gdata.get("probabilities", {}):
                        guild_rules = gdata
                        break

                if guild_rules is None:
                    guild_rules = guilds.get("default", {})

                timer = guild_rules.get("timers", {}).get(cid)
                if timer is None:
                    # no timer configured anymore -> stop worker
                    return

                last_spawn = rules.get("last_spawn", {}).get(cid)
                now = int(time.time())
                # compute sleep time until next allowed spawn
                if last_spawn is None:
                    wait = int(timer)
                else:
                    elapsed = now - int(last_spawn)
                    wait = max(0, int(timer) - int(elapsed))

                # sleep until it's time
                if wait > 0:
                    await asyncio.sleep(wait)

                # reload rules (they may have changed)
                try:
                    rules = await asyncio.to_thread(load_json, "spawn_rules.json", {"guilds": {}, "last_spawn": {}})
                except Exception:
                    rules = {"guilds": {}, "last_spawn": {}}

                guilds = rules.get("guilds", {})
                # recompute guild_rules & probability
                guild_rules = None
                for gid, gdata in guilds.items():
                    if cid in gdata.get("timers", {}) or cid in gdata.get("probabilities", {}):
                        guild_rules = gdata
                        break

                if guild_rules is None:
                    guild_rules = guilds.get("default", {})

                raw_prob = guild_rules.get("probabilities", {}).get(cid, None)
                try:
                    if raw_prob is None:
                        prob = float(RANDOM_DROP_CHANCE)
                    else:
                        prob = float(raw_prob)
                        if prob <= 0:
                            logger.info(f"Channel {cid} has stored probability {raw_prob}; treating as no-specific-rule and using fallback {RANDOM_DROP_CHANCE}")
                            prob = float(RANDOM_DROP_CHANCE)
                except Exception:
                    prob = float(RANDOM_DROP_CHANCE)

                logger.debug(f"Scheduled spawn check for channel {cid}: prob={prob}, timer={timer}, last_spawn={last_spawn}")

                # If timer worker woke, perform an unconditional spawn (timer guarantees drop)
                try:
                    # if this worker ran because wait reached zero, spawn unconditionally
                    channel_id = int(cid)
                    channel = await channel_getter(channel_id)
                    msg, key = await self.summon(channel_id)
                    try:
                        await channel.send(msg)
                    except Exception:
                        pass
                    logger.info(f"Scheduled drop in channel {channel_id}: {key}")

                    rules.setdefault("last_spawn", {})[cid] = int(time.time())
                    try:
                        await asyncio.to_thread(save_json, "spawn_rules.json", rules)
                    except Exception as e:
                        logger.error(f"Failed to save spawn_rules.json: {e}")
                except Exception as e:
                    logger.error(f"Error scheduling drop for channel {cid}: {e}")
                # loop to wait again until next timer
        except asyncio.CancelledError:
            # expected when cancelling the worker
            return
        except Exception as e:
            logger.error(f"Unhandled error in _spawn_worker for {cid}: {e}")

    async def _ensure_spawn_tasks(self, channel_getter):
        """Ensure per-channel spawn worker tasks exist for channels with timers.

        Starts tasks for new channels and cancels tasks for channels whose timers
        have been removed from `spawn_rules.json`.
        """
        try:
            rules = await asyncio.to_thread(load_json, "spawn_rules.json", {"guilds": {}, "last_spawn": {}})
        except Exception:
            rules = {"guilds": {}, "last_spawn": {}}

        guilds = rules.get("guilds", {})
        configured = set()
        for gid, gdata in guilds.items():
            configured.update(map(str, gdata.get("timers", {}).keys()))

        # start tasks for new configured channels
        for cid in configured:
            if cid not in self._spawn_tasks or self._spawn_tasks[cid].done():
                try:
                    task = asyncio.create_task(self._spawn_worker(cid, channel_getter))
                    self._spawn_tasks[cid] = task
                except Exception as e:
                    logger.error(f"Failed to start spawn worker for {cid}: {e}")

        # cancel tasks for channels no longer configured
        for cid in list(self._spawn_tasks.keys()):
            if cid not in configured:
                t = self._spawn_tasks.pop(cid)
                try:
                    t.cancel()
                except Exception:
                    pass

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
    ) -> Tuple[Optional[str], Literal[False] | str]:
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
            caught = self.last_catchable[channel_id]
            del self.last_catchable[channel_id]

        return out, caught

    async def list_inventory(self, user_id: int, category: str ='all') -> str:
        """
        Lists items in a user's inventory.

        Args:
            user_id: User ID

        Returns:
            Message containing inventory
        """
        return await list_inventory(user_id, self.catchables, category)

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
                # Ensure per-channel workers are running for configured timers
                try:
                    await self._ensure_spawn_tasks(channel_getter)
                except Exception as e:
                    logger.error(f"Error ensuring spawn tasks: {e}")

                # Load spawn rules and collect configured channels
                try:
                    rules = await asyncio.to_thread(load_json, "spawn_rules.json", {"guilds": {}, "last_spawn": {}})
                except Exception:
                    rules = {"guilds": {}, "last_spawn": {}}

                guilds = rules.get("guilds", {})
                # gather all channel ids mentioned in probabilities or timers
                channel_ids = set()
                for gid, gdata in guilds.items():
                    channel_ids.update(map(str, gdata.get("probabilities", {}).keys()))
                    channel_ids.update(map(str, gdata.get("timers", {}).keys()))

                # fallback to allowed_channels if nothing configured
                if not channel_ids and allowed_channels:
                    channel_ids = set(str(c) for c in allowed_channels)

                now = int(time.time())

                for cid in list(channel_ids):
                    # skip channels that have a timer: handled by per-channel workers
                    # if a channel has a configured timer, the worker will spawn it exactly when due
                    # so the periodic loop should not attempt to spawn it here
                    has_timer = any(cid in g.get("timers", {}) for g in guilds.values())
                    if has_timer:
                        continue

                for cid in list(channel_ids):
                    try:
                        channel_id = int(cid)
                    except Exception:
                        continue

                    try:
                        # find guild that contains this channel rule, or default
                        guild_rules = None
                        for gid, gdata in guilds.items():
                            if cid in gdata.get("probabilities", {}) or cid in gdata.get("timers", {}):
                                guild_rules = gdata
                                break

                        if guild_rules is None:
                            guild_rules = guilds.get("default", {})

                        timer = guild_rules.get("timers", {}).get(cid)
                        last_spawn = rules.get("last_spawn", {}).get(cid)

                        time_ok = True
                        if timer is not None:
                            if last_spawn is None or (now - int(last_spawn)) >= int(timer):
                                time_ok = True
                            else:
                                time_ok = False

                        raw_prob = guild_rules.get("probabilities", {}).get(cid, None)
                        try:
                            if raw_prob is None:
                                prob = float(RANDOM_DROP_CHANCE)
                            else:
                                prob = float(raw_prob)
                                if prob <= 0:
                                    logger.info(f"Channel {cid} has stored probability {raw_prob}; treating as no-specific-rule and using fallback {RANDOM_DROP_CHANCE}")
                                    prob = float(RANDOM_DROP_CHANCE)
                        except Exception:
                            prob = float(RANDOM_DROP_CHANCE)

                        logger.debug(f"Periodic spawn check for channel {cid}: time_ok={time_ok}, prob={prob}, timer={timer}, last_spawn={last_spawn}")

                        if time_ok and random.random() < float(prob):
                            channel = await channel_getter(channel_id)
                            msg, key = await self.summon(channel_id)
                            try:
                                await channel.send(msg)
                            except Exception:
                                # channel may be DM or unavailable; ignore send errors
                                pass
                            logger.info(f"Random drop in channel {channel_id}: {key}")

                            # update last_spawn timestamp for this channel
                            rules.setdefault("last_spawn", {})[cid] = now
                            try:
                                await asyncio.to_thread(save_json, "spawn_rules.json", rules)
                            except Exception as e:
                                logger.error(f"Failed to save spawn_rules.json: {e}")
                    except Exception as e:
                        logger.error(f"Error processing channel {cid} in random_drop_task: {e}")

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
    # normalize to lowercase for case-insensitive matching
    text: str = text.lower() if isinstance(text, str) else ""
    aliases_lower: Tuple[str, ...] = tuple(a.lower() for a in aliases if isinstance(a, str))
    # Exact substring match first
    for alias, alias_lower in zip(aliases, aliases_lower):
        if alias_lower in text:
            out = f"Caught {key} -> {alias}"
            logger.info(f"User caught {key} with alias '{alias}'")
            return out, True

    # Fuzzy match: check each word in the message against aliases
    # Split on whitespace and punctuation lightly
    words = [w.strip(".,!?;:()[]\"'`)" ) for w in text.split() if w]
    if words and aliases:
        candidate_list = list(aliases)
        for w in words:
            match = find_closest_word(w, candidate_list, threshold=50.0)
            if match:
                out = f"Caught {key} -> {match}"
                logger.info(f"User fuzzy-caught {key}: message word '{w}' matched '{match}'")
                return out, True

    if "catch" in text:
        out = "That is not the right name.."
        logger.debug(f"Failed catch attempt for {key}")

    return out, False


async def drop(
    channel_id: int, catchables: Dict[str, Tuple[str, ...]], user_id: Optional[int] = None
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
            inventory = await db.list_items(user_id, 'all')

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


async def list_inventory(user: int, catchables: Dict[str, Tuple[str, ...]], category: str = 'all') -> str:
    """
    Lists items in a user's inventory.

    Args:
        user: User ID
        catchables: Dictionary of all catchable items

    Returns:
        Message containing inventory
    """
    try:
        items = await db.list_items(user, category)
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


async def get_leaderboard(**kwargs) -> str:
    result = await db.leaderboard(**kwargs)
    if not result:
        return "No users found!"

    output = "## Leaderboard\n"
    emojis = ["🥇", "🥈", "🥉", "⌨️"]

    pos = 0
    for user, count in result.items():
        try:
            prefix = emojis[pos]
        except IndexError:
            prefix = f"**#{pos + 1}**"

        output += f"{prefix} <@{user}>: {count}\n"
        pos += 1

    return output.rstrip()


async def leaderboard_info(**kwargs) -> str:
    try:
        return await get_leaderboard(**kwargs)
    except Exception as e:
        logger.error(f"Error executing inventory command: {e}")
        return "An error occurred while retrieving the xp."


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
        return f"They have {count} items, so their MathDex progression is {round(count * 100 / len(catchables), 2)}%"
    except Exception as e:
        logger.error(f"Error calculating completion: {e}")
        return f"Error calculating completion: {str(e)}"
