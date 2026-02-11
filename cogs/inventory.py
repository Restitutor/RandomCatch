from typing import Literal

import discord
from discord.ext import commands

CATEGORY_MAP: dict[str, list[str]] = {
    "all": [],  # special: no filter
    "numbers": ["numbers1-50", "numbers51-100"],
    "sets": ["sets"],
    "constants": ["constants"],
    "functions": ["functions"],
    "theorems": ["theorems"],
    "symbols": ["symbols"],
    "greek": ["capitalgreek", "smallgreek"],
    "sequences": ["sequence"],
}

CategoryChoice = Literal[
    "all",
    "numbers",
    "sets",
    "constants",
    "functions",
    "theorems",
    "symbols",
    "greek",
    "sequences",
]

DISCORD_MESSAGE_LIMIT = 2000
MEDALS = ["\U0001f947", "\U0001f948", "\U0001f949", "\u2328\ufe0f"]


class InventoryCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _resolve_user(
        self, ctx: commands.Context, user: discord.User | None
    ) -> discord.User | None:
        """Resolve user and validate it's not a bot. Returns None if bot."""
        if user is None:
            user = ctx.author
        if user.bot:
            await ctx.send("That's a bot.")
            return None
        return user

    @commands.hybrid_command(description="Shows user inventory")
    async def inventory(
        self,
        ctx: commands.Context,
        user: discord.User = None,
        category: CategoryChoice = "all",
    ) -> None:
        user = await self._resolve_user(ctx, user)
        if user is None:
            return

        inv = await self.bot.db.get_inventory(user.id)

        if category != "all":
            allowed_categories = CATEGORY_MAP[category]
            inv = {
                k: v
                for k, v in inv.items()
                if self.bot.game.items.get(k) is not None
                and self.bot.game.items[k].category in allowed_categories
            }

        text = "Inventory\n"
        for key, quantity in inv.items():
            item = self.bot.game.items.get(key)
            if item:
                text += f"{key} -> **{item.names.get('en', key)}**: {quantity}\n"

        if len(text.strip()) <= len("Inventory"):
            await ctx.send("Inventory is empty! Catch more math objects!")
            return

        await ctx.send(text[:DISCORD_MESSAGE_LIMIT])

    @commands.hybrid_command(description="Shows user completion percentage")
    async def completion(
        self,
        ctx: commands.Context,
        user: discord.User = None,
    ) -> None:
        user = await self._resolve_user(ctx, user)
        if user is None:
            return

        inv = await self.bot.db.get_inventory(user.id)
        count = len(inv)
        total = len(self.bot.game.items)
        percentage = round(count * 100 / total, 2)

        await ctx.send(
            f"They have {count} items, so their MathDex progression is {percentage}%",
        )

    @commands.hybrid_command(description="Shows remaining items to catch")
    async def remaining(
        self,
        ctx: commands.Context,
        user: discord.User = None,
    ) -> None:
        user = await self._resolve_user(ctx, user)
        if user is None:
            return

        inv = await self.bot.db.get_inventory(user.id)
        remaining_keys = [k for k in self.bot.game.items if k not in inv]

        if not remaining_keys:
            await ctx.send("You caught everything!")
            return

        text = "Remaining\n`" + ", ".join(sorted(remaining_keys)) + "`"
        await ctx.send(text[:DISCORD_MESSAGE_LIMIT])

    @commands.hybrid_command(description="Shows the leaderboard")
    async def leaderboard(self, ctx: commands.Context) -> None:
        lb = await self.bot.db.get_leaderboard()

        if not lb:
            await ctx.send("No users found!")
            return

        text = "## Leaderboard\n"
        for pos, (user, count) in enumerate(lb.items()):
            prefix = MEDALS[pos] if pos < len(MEDALS) else f"**#{pos + 1}**"
            text += f"{prefix} <@{user}>: {count}\n"

        await ctx.send(text[:DISCORD_MESSAGE_LIMIT])

    @commands.hybrid_command(description="Shows total number of catchable objects")
    async def countobjects(self, ctx: commands.Context) -> None:
        await ctx.send(f"There are {len(self.bot.game.items)} to catch!")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InventoryCog(bot))
