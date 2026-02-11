import time
from dataclasses import replace
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from config import ADMIN_IDS
from models import (
    HybridSpawn,
    IntervalSpawn,
    ProbabilitySpawn,
    SpawnRule,
    UserId,
)
from utils import load_json, restart_program, run_git_pull, save_json


class Permissions:
    """Cached permission checker. Loaded from roles.json at init."""

    def __init__(self):
        self.reload()

    def reload(self) -> None:
        data = load_json("roles.json", {"owners": [], "global_admins": []})
        self._owners: frozenset[UserId] = frozenset(data.get("owners", []))
        self._global_admins: frozenset[UserId] = frozenset(
            data.get("global_admins", []),
        )

    def is_owner(self, user_id: UserId) -> bool:
        return user_id in ADMIN_IDS or user_id in self._owners

    def is_admin(self, user_id: UserId, member: discord.Member | None = None) -> bool:
        if self.is_owner(user_id):
            return True
        if user_id in self._global_admins:
            return True
        if member and member.guild_permissions.administrator:
            return True
        return False


class SpawnRules(commands.GroupCog, group_name="spawnrules"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.perms = Permissions()

    def _get_catching_cog(self):
        return self.bot.get_cog("CatchingCog")

    async def _require_admin_and_catching(
        self, interaction: discord.Interaction,
    ) -> tuple[bool, object]:
        if not self.perms.is_admin(interaction.user.id, interaction.user):
            await interaction.response.send_message("Not authorized.", ephemeral=True)
            return (False, None)
        catching = self._get_catching_cog()
        if catching is None:
            await interaction.response.send_message(
                "CatchingCog is not loaded.", ephemeral=True,
            )
            return (False, None)
        return (True, catching)

    @app_commands.command(description="Set per-message spawn probability for a channel")
    async def probability(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        value: float,
    ):
        ok, catching = await self._require_admin_and_catching(interaction)
        if not ok:
            return

        existing = catching._rules.get(channel.id)

        if value <= 0:
            if existing is None:
                await interaction.response.send_message(
                    f"No spawn rule exists for {channel.mention}.",
                    ephemeral=True,
                )
                return
            match existing.mode:
                case ProbabilitySpawn():
                    del catching._rules[channel.id]
                    catching._save_rules()
                    await interaction.response.send_message(
                        f"Removed spawn rule for {channel.mention} "
                        f"(no interval set either).",
                    )
                case HybridSpawn(interval=i):
                    catching._rules[channel.id] = replace(
                        existing, mode=IntervalSpawn(interval=i),
                    )
                    catching._save_rules()
                    await interaction.response.send_message(
                        f"Cleared probability for {channel.mention}. "
                        f"Timed interval ({i}s) remains.",
                    )
                case IntervalSpawn():
                    await interaction.response.send_message(
                        f"{channel.mention} has no probability set.",
                        ephemeral=True,
                    )
        else:
            if value > 1.0:
                await interaction.response.send_message(
                    "Probability must be in (0, 1].", ephemeral=True,
                )
                return
            if existing is not None:
                match existing.mode:
                    case IntervalSpawn(interval=i):
                        new_mode = HybridSpawn(probability=value, interval=i)
                    case _:
                        new_mode = ProbabilitySpawn(probability=value)
                catching._rules[channel.id] = replace(existing, mode=new_mode)
            else:
                catching._rules[channel.id] = SpawnRule(
                    channel_id=channel.id,
                    guild_id=interaction.guild_id,
                    mode=ProbabilitySpawn(probability=value),
                )
            catching._save_rules()
            await interaction.response.send_message(
                f"Set spawn probability for {channel.mention} to {value}.",
            )

    @app_commands.command(description="Set timed drop interval for a channel")
    async def time(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        seconds: int,
    ):
        ok, catching = await self._require_admin_and_catching(interaction)
        if not ok:
            return

        existing = catching._rules.get(channel.id)

        if seconds <= 0:
            if existing is None:
                await interaction.response.send_message(
                    f"No spawn rule exists for {channel.mention}.",
                    ephemeral=True,
                )
                return
            match existing.mode:
                case IntervalSpawn():
                    del catching._rules[channel.id]
                    catching._last_spawn.pop(channel.id, None)
                    catching._save_rules()
                    catching._save_last_spawn()
                    await interaction.response.send_message(
                        f"Removed spawn rule for {channel.mention} "
                        f"(no probability set either).",
                    )
                case HybridSpawn(probability=p):
                    catching._rules[channel.id] = replace(
                        existing, mode=ProbabilitySpawn(probability=p),
                    )
                    catching._last_spawn.pop(channel.id, None)
                    catching._save_rules()
                    catching._save_last_spawn()
                    await interaction.response.send_message(
                        f"Cleared timed interval for {channel.mention}. "
                        f"Probability ({p}) remains.",
                    )
                case ProbabilitySpawn():
                    await interaction.response.send_message(
                        f"{channel.mention} has no interval set.",
                        ephemeral=True,
                    )
        else:
            if seconds > 604800:
                await interaction.response.send_message(
                    "Interval must be in [1, 604800].", ephemeral=True,
                )
                return
            if existing is not None:
                match existing.mode:
                    case ProbabilitySpawn(probability=p):
                        new_mode = HybridSpawn(probability=p, interval=seconds)
                    case _:
                        new_mode = IntervalSpawn(interval=seconds)
                catching._rules[channel.id] = replace(existing, mode=new_mode)
            else:
                catching._rules[channel.id] = SpawnRule(
                    channel_id=channel.id,
                    guild_id=interaction.guild_id,
                    mode=IntervalSpawn(interval=seconds),
                )
            catching._save_rules()
            await interaction.response.send_message(
                f"Set timed drop interval for {channel.mention} to {seconds}s.",
            )

    @app_commands.command(name="list", description="List spawn rules")
    async def list_rules(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
    ):
        ok, catching = await self._require_admin_and_catching(interaction)
        if not ok:
            return

        embed = discord.Embed(title="Spawn Rules", color=discord.Color.blue())

        if channel is not None:
            rule = catching._rules.get(channel.id)
            if rule is None:
                embed.description = f"No spawn rule configured for {channel.mention}."
            else:
                match rule.mode:
                    case ProbabilitySpawn(probability=p):
                        desc = f"Probability: {p}"
                    case IntervalSpawn(interval=i):
                        desc = f"Interval: {i}s"
                    case HybridSpawn(probability=p, interval=i):
                        desc = f"Probability: {p}\nInterval: {i}s"
                embed.add_field(
                    name=f"#{channel.name}",
                    value=f"Channel: {channel.mention}\n{desc}",
                    inline=False,
                )
        else:
            guild_rules = {
                cid: rule
                for cid, rule in catching._rules.items()
                if rule.guild_id == interaction.guild_id
            }
            if not guild_rules:
                embed.description = "No spawn rules configured for this server."
            else:
                for cid, rule in guild_rules.items():
                    match rule.mode:
                        case ProbabilitySpawn(probability=p):
                            desc = f"Probability: {p}"
                        case IntervalSpawn(interval=i):
                            desc = f"Interval: {i}s"
                        case HybridSpawn(probability=p, interval=i):
                            desc = f"Probability: {p}\nInterval: {i}s"
                    embed.add_field(
                        name=f"<#{cid}>",
                        value=desc,
                        inline=False,
                    )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(description="Remove all spawn rules for a channel")
    async def remove(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        ok, catching = await self._require_admin_and_catching(interaction)
        if not ok:
            return

        if channel.id not in catching._rules:
            await interaction.response.send_message(
                f"No spawn rule exists for {channel.mention}.",
                ephemeral=True,
            )
            return

        del catching._rules[channel.id]
        catching._last_spawn.pop(channel.id, None)
        catching._save_rules()
        catching._save_last_spawn()
        await interaction.response.send_message(
            f"Removed all spawn rules for {channel.mention}.",
        )

    @app_commands.command(description="Show spawn timer status")
    async def status(self, interaction: discord.Interaction):
        ok, catching = await self._require_admin_and_catching(interaction)
        if not ok:
            return

        timed_rules = {
            cid: rule
            for cid, rule in catching._rules.items()
            if rule.guild_id == interaction.guild_id
            and isinstance(rule.mode, (IntervalSpawn, HybridSpawn))
        }

        embed = discord.Embed(title="Spawn Timer Status", color=discord.Color.green())

        if not timed_rules:
            embed.description = "No timed spawn rules configured for this server."
        else:
            now = int(time.time())
            for cid, rule in timed_rules.items():
                last = catching._last_spawn.get(cid, 0)
                match rule.mode:
                    case IntervalSpawn(interval=i) | HybridSpawn(interval=i):
                        elapsed = now - last
                        remaining = max(0, i - elapsed)
                        embed.add_field(
                            name=f"<#{cid}>",
                            value=(f"Interval: {i}s\nNext spawn in: {remaining}s"),
                            inline=False,
                        )

        await interaction.response.send_message(embed=embed)


class RoleCog(commands.GroupCog, group_name="role"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.perms = Permissions()

    def _reload_all_perms(self) -> None:
        self.perms.reload()
        for cog in (self.bot.get_cog("SpawnRules"), self.bot.get_cog("AdminCog")):
            if cog is not None and hasattr(cog, "perms"):
                cog.perms.reload()

    @app_commands.command(description="Add a user to a role")
    async def add(
        self,
        interaction: discord.Interaction,
        role: Literal["owner", "global_admin"],
        user: discord.User,
    ):
        if not self.perms.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Only bot owners can manage roles.", ephemeral=True,
            )
            return

        data = load_json("roles.json", {"owners": [], "global_admins": []})
        key = "owners" if role == "owner" else "global_admins"

        if user.id in data[key]:
            await interaction.response.send_message(
                f"{user.mention} already has the **{role}** role.",
                ephemeral=True,
            )
            return

        data[key].append(user.id)
        save_json("roles.json", data)

        self._reload_all_perms()

        await interaction.response.send_message(f"Added {user.mention} to **{role}**.")

    @app_commands.command(description="Remove a user from a role")
    async def remove(
        self,
        interaction: discord.Interaction,
        role: Literal["owner", "global_admin"],
        user: discord.User,
    ):
        if not self.perms.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Only bot owners can manage roles.", ephemeral=True,
            )
            return

        data = load_json("roles.json", {"owners": [], "global_admins": []})
        key = "owners" if role == "owner" else "global_admins"

        if user.id not in data[key]:
            await interaction.response.send_message(
                f"{user.mention} does not have the **{role}** role.",
                ephemeral=True,
            )
            return

        data[key].remove(user.id)
        save_json("roles.json", data)

        self._reload_all_perms()

        await interaction.response.send_message(
            f"Removed {user.mention} from **{role}**.",
        )

    @app_commands.command(name="list", description="List all roles")
    async def list_roles(self, interaction: discord.Interaction):
        if not self.perms.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Only bot owners can view roles.", ephemeral=True,
            )
            return

        data = load_json("roles.json", {"owners": [], "global_admins": []})

        embed = discord.Embed(title="Bot Roles", color=discord.Color.gold())

        owners = data.get("owners", [])
        global_admins = data.get("global_admins", [])

        embed.add_field(
            name="Owners",
            value=("\n".join(f"<@{uid}>" for uid in owners) if owners else "None"),
            inline=False,
        )
        embed.add_field(
            name="Global Admins",
            value=(
                "\n".join(f"<@{uid}>" for uid in global_admins)
                if global_admins
                else "None"
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(description="Reset all roles")
    async def reset(self, interaction: discord.Interaction):
        if not self.perms.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "Only bot owners can reset roles.", ephemeral=True,
            )
            return

        save_json("roles.json", {"owners": [], "global_admins": []})

        self._reload_all_perms()

        await interaction.response.send_message("All roles have been reset.")


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.perms = Permissions()

    @commands.hybrid_command(description="Update bot from git and restart")
    async def updatebot(self, ctx: commands.Context):
        if not self.perms.is_owner(ctx.author.id):
            await ctx.send("Only bot owners can update the bot.")
            return
        status = await run_git_pull()
        await ctx.send("Checked for updates.\n" + status)
        restart_program()


async def setup(bot: commands.Bot):
    await bot.add_cog(SpawnRules(bot))
    await bot.add_cog(RoleCog(bot))
    await bot.add_cog(AdminCog(bot))
