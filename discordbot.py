#!/usr/bin/env python3
import asyncio
import logging
import random

import discord

import math
import inventories
import logic
from reader import read_csv

bot = discord.Bot(
    intents=discord.Intents.none()
    | discord.Intents.message_content
    | discord.Intents.guild_messages,
)

# Channel to ID
ALLOWED_CHANNELS = (1211674089073279106,)

last_catchable: dict[str, str] = {}
catchables = read_csv("data.csv")

PANDA = 502141502038999041
CYCY = 1168452148049231934
RES = 459147358463197185
ADMINS = {CYCY, RES, PANDA}
RANDOM_DROP_TIME = 3600


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


async def list_remaining(user) -> str:
    inv = await inventories.list_items(user)
    items = sorted(set(catchables) - set(inv))
    if items:
        out = "Remaining\n`" + ", ".join(items) + "`"
        return out[:1999]
    else:
        return "You caught everything!"


async def list_inventory(user) -> str:
    items = await inventories.list_items(user)
    if items:
        out = f"Inventory\n"
        for k, names in catchables.items():
            if k not in items:
                continue

            try:
                name = names[0]
                out += f"{k} -> **{name}**: {items[k]}\n"
            except Exception as e:
                print(e)

        return out[:1999]
    else:
        return "Inventory is empty! Catch more math objects!"


async def list_completion(user: str) -> str:
    print("completion", user)
    items = await inventories.list_items(user)
    count = len(items)
    return f"They have {count} items, so their MathDex progression is {round(count*100/len(catchables), 2)}%"


def get_user_id(message) -> str:
    for u in message.mentions:
        if type(u) is discord.member.Member and not u.bot:
            return u.id
    else:
        return message.author.id


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

    if "inventory" in text or "completion" in text or "remaining" in text:
        if "inventory" in text:
            action = list_inventory
        elif "remaining" in text:
            action = list_remaining
        else:
            action = list_completion

        await message.reply(await action(get_user_id(message)))
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

    # Catch event
    user = message.author.id
    if random.random() < 0.02 or (user in ADMINS and "-summon" in text):
        msg = drop(message.channel.id)
        await message.reply(msg)

    if "updatebot" in text:
        if user in ADMINS:
            status = await run_git_pull()
            await message.reply("Checked for updates.\n" + status)
            logic.restart_program()
        else:
            await message.reply("You are not an admin.")
        return


@bot.command()
# pycord will figure out the types for you
async def add(ctx, first: discord.Option(int), second: discord.Option(int)):
    # you can use them as they were actual integers
    sum = first + second
    await ctx.respond(f"The sum of {first} and {second} is {sum}.")


@bot.command()
async def inventory(ctx, user: discord.Option(discord.SlashCommandOptionType.user)):
    print("inventory")
    if user.bot:
        await ctx.respond("That's a bot.")
    else:
        await ctx.respond(await list_inventory(user.id))


@bot.command()
async def completion(ctx, user: discord.Option(discord.SlashCommandOptionType.user)):
    if user.bot:
        await ctx.respond("That's a bot.")
    else:
        await ctx.respond(await list_completion(user.id))


@bot.command()
async def remaining(ctx, user: discord.Option(discord.SlashCommandOptionType.user)):
    if user.bot:
        await ctx.respond("That's a bot.")
    else:
        await ctx.respond(await list_remaining(user.id))


def drop(channel_id) -> str:
    key = random.choice(list(catchables.keys()))
    last_catchable[channel_id] = key
    print("Dropped", key, catchables[key], "in", channel_id)
    return f"A new Math object dropped! `{key}`. Catch it by saying its name!"


@bot.event
async def on_ready():
    await inventories.create_table()
    await inventories.prune_item(tuple(catchables))
    print("Started")
    await bot.wait_until_ready()
    await randomDrop()


async def randomDrop():
    while True:
        if ALLOWED_CHANNELS:
            channel_id = random.choice(ALLOWED_CHANNELS)
            channel = await bot.fetch_channel(channel_id)  # Load into cache
            msg = drop(channel_id)
            await channel.send(msg)
        await asyncio.sleep(RANDOM_DROP_TIME)


if __name__ == "__main__":
    with open("token") as f:
        bot.run(f.read().strip())
