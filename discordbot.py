#!/usr/bin/env python3
"""
Main entry point for the Discord math catch bot.
Integrates all components and handles Discord events.
"""

import asyncio
import random
from typing import Dict

import discord

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
bot = discord.Bot(
    intents=discord.Intents.none()
    | discord.Intents.message_content
    | discord.Intents.guild_messages,
)

# Game state
catchables = {}
last_catchable: Dict[int, str] = {}


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
    global catchables

    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    try:
        # Load catchables
        catchables = game.load_catchables()
        logger.info(f"Loaded {len(catchables)} catchable items")

        # Initialize database
        await db.create_table()
        await db.prune_item(tuple(catchables))

        # Start random drop task
        await bot.wait_until_ready()
        asyncio.create_task(random_drop())

        logger.info("Bot is fully initialized and ready")
    except Exception as e:
        logger.error(f"Error during initialization: {e}")


@bot.event
async def on_message(message):
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

        # Help command
        if "!help" in text:
            await message.reply(
                "Available commands: countobjects, inventory, completion, remaining"
            )
            return

        # Count objects command
        if "countobjects" in text:
            await message.reply(f"There are {len(catchables)} to catch!")
            return

        # Inventory, completion, and remaining commands
        if "inventory" in text or "completion" in text or "remaining" in text:
            if "inventory" in text:
                response = await game.list_inventory(get_user_id(message), catchables)
            elif "remaining" in text:
                response = await game.list_remaining(get_user_id(message), catchables)
            else:
                response = await game.list_completion(get_user_id(message), catchables)

            await message.reply(response)
            return

        # Check for catching attempt
        if message.channel.id in last_catchable:
            key = last_catchable[message.channel.id]
            out, caught = game.try_catch(key, catchables[key], text)

            if out:
                await message.reply(out)

            if caught:
                await db.add_item(message.author.id, key, 1)
                del last_catchable[message.channel.id]

        # Random drop chance on message
        if random.random() < RANDOM_DROP_CHANCE or (
            user in ADMIN_IDS and "-summon" in text
        ):
            msg, key = await game.drop(
                message.channel.id, catchables, message.author.id
            )
            last_catchable[message.channel.id] = key
            await message.reply(msg)

        # Update bot command (git pull and restart)
        if "updatebot" in text:
            if user in ADMIN_IDS:
                status = await utils.run_git_pull()
                await message.reply("Checked for updates.\n" + status)
                utils.restart_program()
            else:
                await message.reply("You are not an admin.")

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        # Don't respond to the user with the error to avoid confusion


@bot.command()
async def inventory(ctx, user: discord.Option(discord.SlashCommandOptionType.user)):
    """
    Slash command to view a user's inventory.

    Args:
        ctx: Command context
        user: User to view inventory for
    """
    try:
        if user.bot:
            await ctx.respond("That's a bot.")
        else:
            await ctx.respond(await game.list_inventory(user.id, catchables))
    except Exception as e:
        logger.error(f"Error executing inventory command: {e}")
        await ctx.respond("An error occurred while retrieving the inventory.")


@bot.command()
async def completion(ctx, user: discord.Option(discord.SlashCommandOptionType.user)):
    """
    Slash command to view a user's completion percentage.

    Args:
        ctx: Command context
        user: User to view completion for
    """
    try:
        if user.bot:
            await ctx.respond("That's a bot.")
        else:
            await ctx.respond(await game.list_completion(user.id, catchables))
    except Exception as e:
        logger.error(f"Error executing completion command: {e}")
        await ctx.respond("An error occurred while calculating completion.")


@bot.command()
async def remaining(ctx, user: discord.Option(discord.SlashCommandOptionType.user)):
    """
    Slash command to view items a user hasn't caught yet.

    Args:
        ctx: Command context
        user: User to view remaining items for
    """
    try:
        if user.bot:
            await ctx.respond("That's a bot.")
        else:
            await ctx.respond(await game.list_remaining(user.id, catchables))
    except Exception as e:
        logger.error(f"Error executing remaining command: {e}")
        await ctx.respond("An error occurred while retrieving remaining items.")


async def random_drop():
    """
    Task that periodically drops random items in allowed channels.
    """
    logger.info("Starting random drop task")

    while True:
        try:
            if ALLOWED_CHANNELS:
                channel_id = random.choice(ALLOWED_CHANNELS)
                channel = await bot.fetch_channel(channel_id)

                msg, key = await game.drop(channel_id, catchables)
                last_catchable[channel_id] = key

                await channel.send(msg)
                logger.info(f"Random drop in channel {channel_id}: {key}")

            await asyncio.sleep(RANDOM_DROP_TIME)
        except Exception as e:
            logger.error(f"Error in random drop task: {e}")
            await asyncio.sleep(60)  # Wait a bit before retrying


if __name__ == "__main__":
    try:
        logger.info("Starting bot")
        bot.run(TOKEN)
    except Exception as e:
        logger.critical(f"Fatal error starting bot: {e}")
