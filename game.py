import difflib
import random
import time

from models import (
    SUMMON_COOLDOWN,
    Catch,
    ChannelId,
    FailedCatch,
    Item,
    ItemKey,
    UserId,
)


class GameState:
    def __init__(self, items: dict[ItemKey, Item]) -> None:
        self.items = items
        self.active: dict[ChannelId, Item] = {}
        self.cooldowns: dict[UserId, float] = {}

    def try_catch(self, channel: ChannelId, text: str) -> Catch | FailedCatch | None:
        item = self.active.get(channel)
        if item is None:
            return None

        # Exact substring match
        matched = item.match(text)
        if matched:
            del self.active[channel]
            return Catch(item=item, matched_name=matched)

        # Fuzzy match for names > 4 chars at 85% cutoff
        text_words = [w.strip(".,!?;:()[]\"'`") for w in text.lower().split() if w]
        all_names = [n for n in item.names.values() if len(n) > 4]
        if all_names and text_words:
            name_map = {n.lower(): n for n in all_names}
            lower_names = list(name_map.keys())
            for word in text_words:
                if len(word) <= 4:
                    continue
                hits = difflib.get_close_matches(
                    word.lower(), lower_names, n=1, cutoff=0.85,
                )
                if hits and hits[0] in name_map:
                    del self.active[channel]
                    return Catch(item=item, matched_name=name_map[hits[0]])

        # Player is trying to catch (used the word "catch") but got the name wrong
        if "catch" in text.lower():
            return FailedCatch()

        return None

    def drop_random(self, channel: ChannelId) -> Item:
        """Drop a uniform random item."""
        key = random.choice(list(self.items.keys()))
        item = self.items[key]
        self.active[channel] = item
        return item

    def drop_favoring_new(self, channel: ChannelId, owned: frozenset[ItemKey]) -> Item:
        """Drop an item, favoring those not in *owned* (10:1 weight)."""
        keys = list(self.items.keys())
        if len(owned) < len(keys):
            weights = [10 if k not in owned else 1 for k in keys]
            key = random.choices(keys, weights=weights, k=1)[0]
        else:
            key = random.choice(keys)
        item = self.items[key]
        self.active[channel] = item
        return item

    def can_summon(self, user: UserId) -> bool:
        return time.time() >= self.cooldowns.get(user, 0)

    def record_summon(self, user: UserId) -> None:
        self.cooldowns[user] = time.time() + SUMMON_COOLDOWN

    def summon_cooldown_remaining(self, user: UserId) -> int:
        return max(0, int(self.cooldowns.get(user, 0) - time.time()))
