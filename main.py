#!/usr/bin/env python3
"""
Main entry point for the Discord math catch bot.
Integrates all components and handles Discord events.
"""

import asyncio
import random

import discord
from discord.ext import bridge

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

        # Random drop chance on message
        if random.random() < RANDOM_DROP_CHANCE:
            msg, _ = await game_state.summon(message.channel.id, message.author.id)
            await message.reply(msg)
        elif "-summon" in text:
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
        if "updatebot" in text:
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
async def inventory(ctx: bridge.BridgeContext, user: discord.User | None):
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
            await ctx.respond(await game_state.list_inventory(user.id))
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


if __name__ == "__main__":
    try:
        logger.info("Starting bot")
        bot.run(TOKEN)
    except Exception as e:
        logger.critical(f"Fatal error starting bot: {e}")
