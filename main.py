import asyncio

import discord
from discord.ext import commands

from config import DATA_FILE, DATABASE, TOKEN
from db import Database
from game import GameState
from items import load_items
from utils import logger

intents = discord.Intents.none()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    allowed_mentions=discord.AllowedMentions(
        everyone=False, users=False, roles=False, replied_user=True
    ),
)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guilds")

    # Log loaded cogs
    logger.info(f"Loaded cogs: {list(bot.cogs.keys())}")

    # Log commands in the tree before syncing
    tree_commands = bot.tree.get_commands()
    logger.info(f"Commands in tree before sync: {[cmd.name for cmd in tree_commands]}")

    # Sync command tree
    try:
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logger.info(f"Synced {len(synced)} commands to {guild.name} ({guild.id}): {[cmd.name for cmd in synced]}")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}", exc_info=True)


async def main():
    async with bot:
        bot.db = Database()
        await bot.db.connect(DATABASE)
        try:
            bot.game = GameState(items=load_items(DATA_FILE))
            await bot.db.prune_items(bot.game.items.keys())

            # Load all extensions before starting the bot
            logger.info("Loading extensions...")
            await bot.load_extension("cogs.catching")
            await bot.load_extension("cogs.inventory")
            await bot.load_extension("cogs.admin")
            logger.info("Extensions loaded successfully")

            # Commands will be synced in on_ready() after bot connects
            await bot.start(TOKEN)
        finally:
            await bot.db.close()


if __name__ == "__main__":
    asyncio.run(main())
