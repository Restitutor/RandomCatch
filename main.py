#!/usr/bin/env python3
"""
Main entry point for the Discord math catch bot.
Integrates all components and handles Discord events.
"""

import asyncio
import random

import discord
from discord.ext import bridge
import time

import game
import db
import utils
from config import (
    TOKEN,
    ALLOWED_CHANNELS,
    ADMIN_IDS,
    RANDOM_DROP_TIME,
    RANDOM_DROP_CHANCE,
)
from utils import logger
from utils import ensure_json_file, load_json, save_json
import asyncio

# Bot setup
bot = bridge.Bot(
    allowed_mentions=discord.AllowedMentions.none(),
    command_prefix="!",
    intents=discord.Intents.none()
    | discord.Intents.message_content
    | discord.Intents.guild_messages,
)

# Game instance
game_state = game.GameState()


def get_user_id(message) -> int:
    """
    Gets the user ID from a message, prioritizing mentioned users.

    Args:
        message: Discord message

    Returns:
        User ID
    """
    for u in message.mentions:
        if isinstance(u, discord.member.Member) and not u.bot:
            return u.id

    return message.author.id


@bot.event
async def on_ready():
    """
    Called when the bot is ready.
    Initializes database and starts random drop task.
    """
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    try:
        # Initialize game state and database
        game_state.initialize()
        await db.create_table()
        await db.prune_item(tuple(game_state.catchables))

        # Ensure persistent JSON files exist
        ensure_json_file("roles.json", {"owners": [], "global_admins": []})
        ensure_json_file(
            "spawn_rules.json",
            {"guilds": {"default": {"probabilities": {}, "timers": {}}}, "last_spawn": {}},
        )

        # Start random drop task
        await bot.wait_until_ready()
        await bot.sync_commands()
        asyncio.create_task(
            game_state.random_drop_task(
                bot.fetch_channel, ALLOWED_CHANNELS, RANDOM_DROP_TIME
            )
        )

        logger.info("Bot is fully initialized and ready")
    except Exception as e:
        logger.error(f"Error during initialization: {e}")


@bot.listen("on_message")
async def on_text_message(message):
    """
    Processes incoming messages.
    Handles commands and catching mechanics.

    Args:
        message: Discord message
    """
    # Ignore bot messages and DMs
    if message.author.bot or not isinstance(message.author, discord.member.Member):
        return

    try:
        text = message.clean_content
        user = message.author.id

        # Check for catching attempt
        out, caught = game_state.try_catch_in_channel(message.channel.id, text)
        if out:
            await message.reply(out)
        if caught:
            await db.add_item(message.author.id, caught, 1)

        # Random drop chance on message (consult spawn_rules.json)
        try:
            rules = await asyncio.to_thread(load_json, "spawn_rules.json", {"guilds": {}, "last_spawn": {}})
            gid = str(getattr(message.guild, "id", None)) if getattr(message, "guild", None) is not None else "default"
            guild_rules = rules.get("guilds", {}).get(gid, rules.get("guilds", {}).get("default", {}))
            cid = str(message.channel.id)

            # Check time-based rule
            timer = guild_rules.get("timers", {}).get(cid)
            last_spawn = rules.get("last_spawn", {}).get(cid)
            now = int(time.time())
            time_ok = True
            if timer is not None:
                if last_spawn is None or (now - int(last_spawn)) >= int(timer):
                    time_ok = True
                else:
                    time_ok = False

            # Check probability rule (treat missing or non-positive as fallback to global RANDOM_DROP_CHANCE)
            raw_prob = guild_rules.get("probabilities", {}).get(cid)
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

            logger.debug(f"Spawn check for channel {cid}: time_ok={time_ok}, prob={prob}, timer={timer}, last_spawn={last_spawn}")

            # If a timer exists and time is elapsed, force a spawn regardless of probability
            if timer is not None and time_ok:
                msg, _ = await game_state.summon(message.channel.id, message.author.id)
                await message.reply(msg)
                logger.info(f"Timer-forced spawn in channel {cid} for user {message.author.id} (timer={timer})")
                # update last_spawn for channel
                rules.setdefault("last_spawn", {})[cid] = now
                await asyncio.to_thread(save_json, "spawn_rules.json", rules)
            elif random.random() < float(prob):
                msg, _ = await game_state.summon(message.channel.id, message.author.id)
                await message.reply(msg)
                logger.info(f"Spawned in channel {cid} for user {message.author.id} (prob={prob}, timer={timer})")
                # update last_spawn for channel
                rules.setdefault("last_spawn", {})[cid] = now
                await asyncio.to_thread(save_json, "spawn_rules.json", rules)
            else:
                logger.debug(f"No spawn in channel {cid}: time_ok={time_ok}, prob={prob}, timer={timer}")
        except Exception as e:
            logger.error(f"Error checking spawn rules: {e}")

        # Manual summon trigger
        if "-summon" in text:
            if game_state.can_summon(message.author.id):
                msg = f"{message.author} used their summon!\n"
                summon_msg, _ = await game_state.summon(
                    message.channel.id, message.author.id
                )
                msg += summon_msg
                await message.reply(msg)
            else:
                sec = game_state.get_summon_cooldown(user)
                await message.reply(f"You must wait {sec} seconds!")

        # Update bot command (git pull and restart)
        if "updatedebug" in text:
            if user in ADMIN_IDS:
                status = await utils.run_git_pull()
                await message.reply("Checked for updates.\n" + status)
                utils.restart_program()
            else:
                await message.reply("You are not an admin.")

    except Exception as e:
        logger.exception(f"Error processing message: {e}")


@bot.bridge_command(description="Shows user inventory.")
@bridge.bridge_option(
    "user", input_type=discord.SlashCommandOptionType.user, required=False
)
@bridge.bridge_option(
    "category", input_type=discord.SlashCommandOptionType.string, required=False
)
async def inventory(ctx: bridge.BridgeContext, user: discord.User | None, category: str = 'all'):
    """
    Slash command to view a user's inventory.

    Args:
        ctx: Command context
        user: User to view inventory for
    """
    if user is None:
        user = ctx.author
    try:
        if user.bot:
            await ctx.respond("That's a bot.")
        else:
            await ctx.respond(await game_state.list_inventory(user.id, category=category))
    except Exception as e:
        logger.error(f"Error executing inventory command: {e}")
        await ctx.respond("An error occurred while retrieving the inventory.")


@bot.bridge_command(description="Shows user completion percentage.")
@bridge.bridge_option(
    "user", input_type=discord.SlashCommandOptionType.user, required=False
)
async def completion(ctx: bridge.BridgeContext, user: discord.User | None):
    """
    Slash command to view a user's completion percentage.

    Args:
        ctx: Command context
        user: User to view completion for
    """
    if user is None:
        user = ctx.author
    try:
        if user.bot:
            await ctx.respond("That's a bot.")
        else:
            await ctx.respond(await game_state.list_completion(user.id))
    except Exception as e:
        logger.error(f"Error executing completion command: {e}")
        await ctx.respond("An error occurred while calculating completion.")


@bot.bridge_command(description="Shows user remaining items.")
@bridge.bridge_option(
    "user", input_type=discord.SlashCommandOptionType.user, required=False
)
async def remaining(ctx: bridge.BridgeContext, user: discord.User | None):
    """
    Slash command to view items a user hasn't caught yet.

    Args:
        ctx: Command context
        user: User to view remaining items for
    """
    if user is None:
        user = ctx.author
    try:
        if user.bot:
            await ctx.respond("That's a bot.")
        else:
            await ctx.respond(await game_state.list_remaining(user.id))
    except Exception as e:
        logger.error(f"Error executing remaining command: {e}")
        await ctx.respond("An error occurred while retrieving remaining items.")


@bot.bridge_command()
async def leaderboard(ctx):
    await ctx.respond(await game.leaderboard_info())


@bot.bridge_command()
async def countobjects(ctx):
    await ctx.respond(f"There are {len(game_state.catchables)} to catch!")


@bot.bridge_command(description="Show spawn rules and next-run times for this guild (admins only)")
async def spawnstatus(ctx: bridge.BridgeContext):
    author, guild_id = resolve_ctx_author_and_guild(ctx)
    if not await has_server_admin_permission(author, guild_id):
        await ctx.respond("You need to be a server administrator or global admin to view spawn status.")
        return

    gid = str(guild_id) if guild_id is not None else "default"
    rules = await asyncio.to_thread(load_json, "spawn_rules.json", {"guilds": {}, "last_spawn": {}})
    guild_rules = rules.get("guilds", {}).get(gid, rules.get("guilds", {}).get("default", {}))
    timers = guild_rules.get("timers", {})
    last_spawn = rules.get("last_spawn", {})
    now = int(time.time())

    lines = []
    if not timers:
        await ctx.respond(f"No timers configured for guild {gid}.")
        return

    for cid, interval in timers.items():
        ls = last_spawn.get(cid)
        if ls is None:
            next_run = f"in {interval} seconds"
        else:
            elapsed = now - int(ls)
            remaining = max(0, int(interval) - int(elapsed))
            next_run = f"in {remaining} seconds"
        prob = guild_rules.get("probabilities", {}).get(cid, RANDOM_DROP_CHANCE)
        lines.append(f"Channel {cid}: interval={interval}s, next={next_run}, prob={prob}")

    await ctx.respond("\n".join(lines))


async def is_owner(user_id: int) -> bool:
    """Return True if user_id is an owner (either in ADMIN_IDS or in roles.json owners)."""
    try:
        roles = await asyncio.to_thread(load_json, "roles.json", {"owners": [], "global_admins": []})
        owners = set(roles.get("owners", []))
        return user_id in ADMIN_IDS or user_id in owners
    except Exception:
        return user_id in ADMIN_IDS


def resolve_ctx_author_and_guild(ctx):
    """Robustly resolve author (Member/User) and guild id from a BridgeContext."""
    author = getattr(ctx, "author", None) or getattr(ctx, "user", None)
    if author is None:
        inter = getattr(ctx, "interaction", None)
        if inter is not None:
            author = getattr(inter, "user", None)

    guild = getattr(ctx, "guild", None)
    guild_id = None
    if guild is not None:
        guild_id = getattr(guild, "id", None)
    else:
        guild_id = getattr(ctx, "guild_id", None) or getattr(ctx, "guild_id", None)

    return author, guild_id


async def has_server_admin_permission(author, guild_id) -> bool:
    """Return True if the author is a guild administrator or a global admin/owner."""
    try:
        # Global admin shortcut
        roles = await asyncio.to_thread(load_json, "roles.json", {"owners": [], "global_admins": []})
        global_admins = set(roles.get("global_admins", []))
        if getattr(author, "id", None) in ADMIN_IDS or getattr(author, "id", None) in global_admins:
            return True

        # If author has guild permissions, check administrator flag
        perms = getattr(author, "guild_permissions", None)
        if perms is not None and getattr(perms, "administrator", False):
            return True

    except Exception:
        pass

    return False


@bot.bridge_command(description="Manage spawn rules (probability/time). Server admins or global admins only.")
@bridge.bridge_option("action", input_type=discord.SlashCommandOptionType.string, required=True)
@bridge.bridge_option("channel", input_type=discord.SlashCommandOptionType.string, required=False)
@bridge.bridge_option("value", input_type=discord.SlashCommandOptionType.string, required=False)
async def spawnrules(ctx: bridge.BridgeContext, action: str, channel: str | int | None = None, value: str | None = None):
    """Configure spawn rules per-guild and per-channel.

    Actions:
      - probability <channel> <float>
      - time <channel> <seconds>
      - list [channel]
      - remove <channel> (removes both probability and time)
    """
    author, guild_id = resolve_ctx_author_and_guild(ctx)
    author_id = getattr(author, "id", None)
    if author_id is None:
        await ctx.respond("Unable to resolve command author.")
        return

    if not await has_server_admin_permission(author, guild_id):
        await ctx.respond("You need to be a server administrator or global admin to change spawn rules.")
        return

    rules = await asyncio.to_thread(load_json, "spawn_rules.json", {"guilds": {}, "last_spawn": {}})
    gid = str(guild_id) if guild_id is not None else "default"
    guild_rules = rules.setdefault("guilds", {}).setdefault(gid, {"probabilities": {}, "timers": {}})

    action = action.lower()
    # Helper: if channel option was not provided, try to resolve a channel id from the value string
    async def try_resolve_channel(opt_channel, opt_value):
        # If opt_channel is already a channel-like object, return it
        if opt_channel is not None and not isinstance(opt_channel, (str, int)):
            return opt_channel, opt_value

        # If opt_channel provided as string/int, try to parse it as an id/mention/name
        if isinstance(opt_channel, int) or (isinstance(opt_channel, str) and opt_channel.strip()):
            # feed the combined representation into the same parsing logic below
            combined = str(opt_channel)
            if opt_value:
                combined = combined + " " + str(opt_value)
            opt_value = combined

        if not opt_value:
            return None, opt_value

        import re

        # Try <#123456789> style mention
        m = re.search(r"<#(\d+)>", str(opt_value))
        if m:
            cid = int(m.group(1))
            # prefer cached channel first
            ch = bot.get_channel(cid)
            if ch is None:
                try:
                    ch = await bot.fetch_channel(cid)
                except Exception as e:
                    logger.warning(f"Failed to fetch channel {cid} from mention: {e}")
                    return None, opt_value

            # remove the mention part from value
            new_val = re.sub(r"<#\d+>", "", str(opt_value)).strip()
            return ch, new_val if new_val else None

        # Try '12345 rest' style: leading id then value
        parts = str(opt_value).strip().split(None, 1)
        if parts and parts[0].isdigit():
            cid = int(parts[0])
            # prefer cached channel first
            ch = bot.get_channel(cid)
            if ch is None:
                try:
                    ch = await bot.fetch_channel(cid)
                except Exception as e:
                    logger.warning(f"Failed to fetch channel {cid} from numeric prefix: {e}")
                    return None, opt_value

            new_val = parts[1] if len(parts) > 1 else None
            return ch, new_val

    # Try '#channelname' style (name only)
        val = str(opt_value).strip()
        if val.startswith("#"):
            name = val.lstrip("#").split(None, 1)[0]
            try:
                # try to find in the guild cache
                g = None
                if gid != "default":
                    try:
                        g = bot.get_guild(int(gid))
                    except Exception:
                        g = None

                if g is not None:
                    for ch in g.channels:
                        if getattr(ch, "name", "").lower() == name.lower():
                            # strip the channel name from the value
                            rest = val.split(None, 1)[1] if len(val.split(None, 1)) > 1 else None
                            return ch, rest
            except Exception as e:
                logger.warning(f"Failed to resolve channel by name '{name}': {e}")
                return None, opt_value

        return None, opt_value


    # Try to recover channel from options if missing
    channel, value = await try_resolve_channel(channel, value)
    if channel is None and action in ("probability", "time", "remove"):
        await ctx.respond("Could not resolve the channel. Provide a channel option, a channel mention like <#id>, or prefix the value with the channel id.")
        logger.warning(f"{author} attempted to set spawnrule but channel could not be resolved. value={value}")
        return

    if action == "list":
        if channel is None:
            await ctx.respond(f"Spawn rules for guild {gid}: {guild_rules}")
            logger.info(f"{author} requested spawn rules for guild {gid}")
        else:
            cid = str(channel.id)
            p = guild_rules.get("probabilities", {}).get(cid)
            t = guild_rules.get("timers", {}).get(cid)
            await ctx.respond(f"Channel {cid} -> probability={p}, time={t}")
            logger.info(f"{author} requested spawn rules for channel {cid} in guild {gid}")
        return

    if action == "remove":
        if channel is None:
            await ctx.respond("You must provide a channel to remove rules for.")
            return
        cid = str(channel.id)
        guild_rules.get("probabilities", {}).pop(cid, None)
        guild_rules.get("timers", {}).pop(cid, None)
        rules.setdefault("guilds", {})[gid] = guild_rules
        await asyncio.to_thread(save_json, "spawn_rules.json", rules)
        await ctx.respond(f"Removed rules for channel {cid}.")
        logger.info(f"{author} removed spawn rules for channel {cid} in guild {gid}")
        return

    if action in ("probability", "time"):
        if channel is None or value is None:
            await ctx.respond("You must provide a channel and a value.")
            return

        cid = str(channel.id)
        try:
            if action == "probability":
                v = float(value)
                if v <= 0:
                    guild_rules.get("probabilities", {}).pop(cid, None)
                    resp = f"Removed probability rule for channel {cid}."
                else:
                    # Clamp to [0.0, 1.0]
                    v = max(0.0, min(1.0, v))
                    guild_rules.setdefault("probabilities", {})[cid] = v
                    resp = f"Set probability for channel {cid} to {v}."
            else:
                v = int(value)
                if v <= 0:
                    guild_rules.get("timers", {}).pop(cid, None)
                    resp = f"Removed time rule for channel {cid}."
                else:
                    # clamp timer to a max of 7 days = 604800 seconds to avoid overflow
                    v = max(1, min(604800, v))
                    guild_rules.setdefault("timers", {})[cid] = v
                    resp = f"Set time interval for channel {cid} to {v} seconds."

            rules.setdefault("guilds", {})[gid] = guild_rules
            await asyncio.to_thread(save_json, "spawn_rules.json", rules)
            await ctx.respond(resp)
            logger.info(f"{author} set spawn rule in guild {gid}: {resp}")
            return
        except ValueError:
            await ctx.respond("Invalid value type. Probability must be a float, time must be an integer.")
            return

    await ctx.respond("Unknown action. Use probability/time/list/remove.")


@bot.bridge_command(description="Manage bot roles (owners/global_admins). Owner-only.")
@bridge.bridge_option("action", input_type=discord.SlashCommandOptionType.string, required=True)
@bridge.bridge_option("role", input_type=discord.SlashCommandOptionType.string, required=False)
@bridge.bridge_option("user", input_type=discord.SlashCommandOptionType.user, required=False)
async def role(ctx: bridge.BridgeContext, action: str, role: str | None = None, user: discord.User | None = None):
    """Manage roles stored in `roles.json`.

    Actions:
      - add: add a user to a role (role param: owners|global_admins)
      - remove: remove a user from a role
      - list: list current roles
      - reset: clear roles
    """
    # BridgeContext typing varies; resolve author id robustly
    author = getattr(ctx, "author", None) or getattr(ctx, "user", None)
    if author is None and getattr(ctx, "interaction", None) is not None:
        author = getattr(ctx.interaction, "user", None)
    author_id = getattr(author, "id", None)
    if author_id is None:
        await ctx.respond("Unable to resolve the command author.")
        return
    if not await is_owner(author_id):
        await ctx.respond("Only bot owners can manage roles.")
        return

    data = await asyncio.to_thread(load_json, "roles.json", {"owners": [], "global_admins": []})

    action = action.lower()
    if action == "list":
        await ctx.respond(f"Roles: {data}")
        logger.info(f"{author} listed roles: {data}")
        return

    if action == "reset":
        data = {"owners": [], "global_admins": []}
        await asyncio.to_thread(save_json, "roles.json", data)
        await ctx.respond("Roles reset to empty.")
        logger.info(f"{author} reset all roles")
        return

    if action in ("add", "remove"):
        if role not in ("owners", "global_admins"):
            await ctx.respond("Role must be 'owners' or 'global_admins'.")
            return

        if user is None:
            await ctx.respond("You must provide a user to add/remove.")
            return

        uid = user.id
        members = set(data.get(role, []))
        if action == "add":
            members.add(uid)
            data[role] = list(members)
            await asyncio.to_thread(save_json, "roles.json", data)
            await ctx.respond(f"Added {user} to {role} by {author}.")
            logger.info(f"{author} added user {uid} to role {role}")
            return
        else:
            if uid in members:
                members.remove(uid)
                data[role] = list(members)
                await asyncio.to_thread(save_json, "roles.json", data)
                await ctx.respond(f"Removed {user} from {role} by {author}.")
                logger.info(f"{author} removed user {uid} from role {role}")
            else:
                await ctx.respond(f"User not in {role}.")
            return

    await ctx.respond("Unknown action. Use add/remove/list/reset.")


if __name__ == "__main__":
    try:
        logger.info("Starting bot")
        bot.run(TOKEN)
    except Exception as e:
        logger.critical(f"Fatal error starting bot: {e}")
