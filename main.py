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


class RandomCatchBot(commands.Bot):
    async def setup_hook(self) -> None:
        self.db = Database()
        await self.db.connect(DATABASE)

        self.game = GameState(items=load_items(DATA_FILE))
        await self.db.prune_items(self.game.items.keys())

        logger.info("Loading extensions...")
        await self.load_extension("cogs.catching")
        print("After catching:", [c.name for c in self.tree.get_commands()])
        await self.load_extension("cogs.inventory")
        print("After inventory:", [c.name for c in self.tree.get_commands()])
        await self.load_extension("cogs.admin")
        print("After admin:", [c.name for c in self.tree.get_commands()])
        logger.info("Extensions loaded successfully")

        tree_commands = self.tree.get_commands()
        logger.info(
            f"Commands in tree before sync: {[cmd.name for cmd in tree_commands]}",
        )

        GUILD = discord.Object(id=1168466989489078302)
        self.tree.copy_global_to(guild=GUILD)
        synced = await self.tree.sync(guild=GUILD)
        print(f"Guild synced {len(synced)}: {[c.name for c in synced]}")

        # Now immediately read back from the API to confirm
        cmds = await self.tree.fetch_commands(guild=GUILD)
        print(f"API confirms {len(cmds)} guild commands: {[c.name for c in cmds]}")

        import aiohttp

        app_info = await self.application_info()
        print(f"Actual app ID: {app_info.id}")
        async with aiohttp.ClientSession() as session, session.get(
            f"https://discord.com/api/v10/applications/{app_info.id}/commands",
            headers={"Authorization": f"Bot {TOKEN}"},
        ) as r:
            data = await r.json()
            print(
                f"API sees {len(data)} global commands: {[c['name'] for c in data]}",
            )

    async def on_ready(self) -> None:
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        logger.info(f"Loaded cogs: {list(self.cogs.keys())}")

    async def close(self) -> None:
        await self.db.close()
        await super().close()


bot = RandomCatchBot(
    command_prefix="!",
    intents=intents,
    allowed_mentions=discord.AllowedMentions(
        everyone=False, users=False, roles=False, replied_user=True,
    ),
)


async def main() -> None:
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
