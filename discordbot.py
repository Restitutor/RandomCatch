#!/home/onfim/env/bin/python
#!/usr/bin/env python3
import asyncio
import logging
import random

import discord

import inventories
import logic
from reader import read_csv

bot = discord.Bot(
    intents=discord.Intents.none()
    | discord.Intents.message_content
    | discord.Intents.guild_messages,
)

# Channel to ID
last_catchable: dict[str, str] = {}
catchables = read_csv("data.csv")

CYCY = 1168452148049231934
RES = 459147358463197185
ADMINS = {CYCY, RES}


async def run_git_pull() -> str:
    process = await asyncio.create_subprocess_exec(
        "git",
        "pull",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if stderr:
        logging.error(stderr)

    return stdout.decode().strip()


@bot.event
async def on_message(message):
    # Limit to people in guilds
    if message.author.bot or type(message.author) is not discord.member.Member:
        return

    text = message.clean_content

    if "!help" in text:
        await message.reply("Available commands: countobjects, inventory")
        return

    if "countobjects" in text:
        await message.reply(f"There are {len(catchables)} to catch!")
        return

    if "inventory" in text:
        items = await inventories.list_items(message.author.id)
        if items:
            out = "Your Inventory\n"
            for k, v in items.items():
                name = catchables[k][0]
                out += f"{k} -> **{name}**: {v}\n"

            await message.reply(out[:2000])
        else:
            await message.reply("Your inventory is empty! Catch more math objects!")
        return

    # Check catch first
    if message.channel.id in last_catchable:
        key = last_catchable[message.channel.id]
        out, caught = logic.try_catch(key, catchables[key], text)
        if out:
            await message.reply(out)
        if caught:
            await inventories.add_item(message.author.id, key, 1)
            del last_catchable[message.channel.id]

    if random.random() < 0.05:
        key = random.choice(list(catchables.keys()))
        last_catchable[message.channel.id] = key
        print("Dropped", key, catchables[key], "in", message.channel.id)
        await message.reply(
            f"A new Math object dropped! `{key}`. Catch it by saying its name!",
        )
        # Catch event

    user = message.author.id
    if "updatebot" in text:
        if user in ADMINS:
            status = await run_git_pull()
            await message.reply("Checked for updates.\n" + status)
            logic.restart_program()
        else:
            await message.reply("You are not an admin.")
        return


@bot.event
async def on_ready():
    await inventories.create_table()
    print("Started")


bot.run("TOKEN")
