import random
import time

import discord
from discord.ext import commands, tasks

from config import ADMIN_IDS, RANDOM_DROP_CHANCE
from models import (
    ChannelId,
    FailedCatch,
    HybridSpawn,
    IntervalSpawn,
    ProbabilitySpawn,
    SpawnRule,
)
from utils import load_json, logger, save_json

SPAWN_RULES_FILE = "spawn_rules.json"
LAST_SPAWN_FILE = "last_spawn.json"


def _parse_mode(info: dict) -> ProbabilitySpawn | IntervalSpawn | HybridSpawn:
    prob = float(info.get("probability", 0.0))
    interval = int(info.get("interval", 0))
    has_prob = prob > 0.0
    has_interval = interval > 0
    if has_prob and has_interval:
        return HybridSpawn(probability=prob, interval=interval)
    if has_prob:
        return ProbabilitySpawn(probability=prob)
    if has_interval:
        return IntervalSpawn(interval=interval)
    raise ValueError(f"Invalid spawn rule: probability={prob}, interval={interval}")


def _serialize_mode(mode: ProbabilitySpawn | IntervalSpawn | HybridSpawn) -> dict:
    match mode:
        case ProbabilitySpawn(probability=p):
            return {"probability": p, "interval": 0}
        case IntervalSpawn(interval=i):
            return {"probability": 0.0, "interval": i}
        case HybridSpawn(probability=p, interval=i):
            return {"probability": p, "interval": i}


class CatchingCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._rules: dict[ChannelId, SpawnRule] = {}
        self._last_spawn: dict[ChannelId, int] = {}
        self._load_rules()
        self._load_last_spawn()

    def _load_rules(self) -> None:
        data = load_json(SPAWN_RULES_FILE)
        self._rules = {}

        # Try new format first: {"rules": {"channel_id": {...}}}
        if "rules" in data and isinstance(data["rules"], dict):
            rules_raw = data["rules"]
        # Try intermediate format: {channel_id: {...}} directly
        elif isinstance(data, dict) and data and all(
            isinstance(k, str) and k.isdigit() for k in data.keys()
        ):
            rules_raw = data
        else:
            # Old format (nested by guild) or unrecognized—skip
            logger.warning(
                "Could not parse spawn_rules.json; skipping rules. "
                "Format may be from an older version."
            )
            return

        for cid_str, info in rules_raw.items():
            if not isinstance(info, dict):
                logger.warning("Skipping malformed rule for channel %s", cid_str)
                continue
            try:
                cid = int(cid_str)
                mode = _parse_mode(info)
            except (ValueError, TypeError) as e:
                logger.warning(
                    "Skipping invalid spawn rule for channel %s: %s", cid_str, e
                )
                continue
            self._rules[cid] = SpawnRule(
                channel_id=cid,
                guild_id=int(info.get("guild_id", 0)),
                mode=mode,
            )

    def _save_rules(self) -> None:
        rules_out: dict[str, dict] = {}
        for cid, rule in self._rules.items():
            out = {"guild_id": rule.guild_id}
            out.update(_serialize_mode(rule.mode))
            rules_out[str(cid)] = out
        save_json(SPAWN_RULES_FILE, {"rules": rules_out})

    def _load_last_spawn(self) -> None:
        # Fall back to old format in spawn_rules.json for migration
        data = load_json(LAST_SPAWN_FILE)
        if not data:
            old = load_json(SPAWN_RULES_FILE)
            data = old.get("last_spawn", {})
        self._last_spawn = {int(k): int(v) for k, v in data.items()}

    def _save_last_spawn(self) -> None:
        save_json(LAST_SPAWN_FILE, {str(k): v for k, v in self._last_spawn.items()})

    @staticmethod
    def _drop_message(item) -> str:
        return f"A new Math object dropped! `{item.key}`. Catch it by saying its name!"

    async def _get_owned_keys(self, user_id: int) -> frozenset[str]:
        inv = await self.bot.db.get_inventory(user_id)
        return frozenset(inv.keys())

    @commands.Cog.listener("on_message")
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        channel_id = message.channel.id

        # Skip catch check for prefix commands to avoid false matches (e.g. "sum" in "!summon" catching ∑)
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        result = self.bot.game.try_catch(channel_id, message.clean_content)
        if isinstance(result, FailedCatch):
            await message.reply("That is not the right name..")
            return
        elif result is not None:
            await self.bot.db.add_item(message.author.id, result.item.key)
            await message.reply(
                f"Caught {result.item.key} -> {result.matched_name}"
            )
            return  # no spawn on the same message that catches

        rule = self._rules.get(channel_id)
        if rule is not None:
            match rule.mode:
                case ProbabilitySpawn(probability=p) | HybridSpawn(probability=p):
                    if random.random() < p:
                        owned = await self._get_owned_keys(message.author.id)
                        item = self.bot.game.drop_favoring_new(channel_id, owned)
                        self._last_spawn[channel_id] = int(time.time())
                        self._save_last_spawn()
                        await message.reply(self._drop_message(item))
                        return
                case IntervalSpawn():
                    pass  # no per-message spawn
        elif random.random() < RANDOM_DROP_CHANCE:
            owned = await self._get_owned_keys(message.author.id)
            item = self.bot.game.drop_favoring_new(channel_id, owned)
            self._last_spawn[channel_id] = int(time.time())
            self._save_last_spawn()
            await message.reply(self._drop_message(item))

    @tasks.loop(seconds=30)
    async def timed_drop(self) -> None:
        now = int(time.time())
        for rule in list(self._rules.values()):
            match rule.mode:
                case IntervalSpawn(interval=i) | HybridSpawn(interval=i):
                    last = self._last_spawn.get(rule.channel_id, 0)
                    if now - last < i:
                        continue
                    try:
                        channel = self.bot.get_channel(rule.channel_id)
                        if channel is None:
                            channel = await self.bot.fetch_channel(rule.channel_id)
                        item = self.bot.game.drop_random(rule.channel_id)
                        await channel.send(self._drop_message(item))
                        self._last_spawn[rule.channel_id] = now
                        self._save_last_spawn()
                    except Exception:
                        logger.exception(
                            "Timed drop failed for channel %s", rule.channel_id,
                        )
                case ProbabilitySpawn():
                    pass  # no timed spawn

    @timed_drop.before_loop
    async def _before_timed_drop(self) -> None:
        await self.bot.wait_until_ready()

    async def cog_load(self) -> None:
        self.timed_drop.start()

    async def cog_unload(self) -> None:
        self.timed_drop.cancel()

    @commands.hybrid_command(description="Summon a random math object")
    async def summon(self, ctx: commands.Context) -> None:
        if ctx.guild is None:
            return

        user_id = ctx.author.id
        is_admin = user_id in ADMIN_IDS

        if not is_admin and not self.bot.game.can_summon(user_id):
            remaining = self.bot.game.summon_cooldown_remaining(user_id)
            await ctx.send(f"You must wait {remaining} seconds!")
            return

        self.bot.game.record_summon(user_id)
        owned = await self._get_owned_keys(user_id)
        item = self.bot.game.drop_favoring_new(ctx.channel.id, owned)
        msg = f"{ctx.author} used their summon!\n{self._drop_message(item)}"
        await ctx.send(msg)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CatchingCog(bot))
