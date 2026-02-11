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
bot._synced = False


@bot.event
async def on_ready():
    if not bot._synced:
        await bot.tree.sync()
        bot._synced = True
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")


async def main():
    async with bot:
        bot.db = Database()
        await bot.db.connect(DATABASE)
        try:
            bot.game = GameState(items=load_items(DATA_FILE))
            await bot.db.prune_items(bot.game.items.keys())
            await bot.load_extension("cogs.catching")
            await bot.load_extension("cogs.inventory")
            await bot.load_extension("cogs.admin")
            await bot.start(TOKEN)
        finally:
            await bot.db.close()


if __name__ == "__main__":
    asyncio.run(main())
