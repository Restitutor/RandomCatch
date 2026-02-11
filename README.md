# Math Catch Discord Bot

A Discord bot that allows users to catch math objects that randomly appear in designated channels.

## Project Structure

```
├── discordbot.py    # Main entry point and Discord event handling
├── config.py        # Centralized configuration
├── db.py            # Database operations
├── game.py          # Game mechanics and logic
├── utils.py         # Utility functions
├── data.csv         # CSV file containing catchable items
├── token            # Discord bot token (has to be added)
└── inventory.db     # SQLite database for storing user inventories
```

## How to Run

1. Ensure you have uv installed:
   ```
   pip install uv
   ```

2. Make sure you have a valid Discord bot token in a file named `token`

3. Run the bot:
   ```
   uv run bot.py
   ```
   if you're running the first time, else a normal run will do:
   ```
   python bot.py
   ```

4. Running tests

   Install pytest and run the tests:
   ```
   python -m pip install -U pytest
   pytest -q
   ```

## Commands

- `!help` - Shows available commands
- `countobjects` - Shows the total number of catchable objects
- `inventory` - Shows a user's inventory
- `completion` - Shows a user's completion percentage
- `remaining` - Shows what a user hasn't caught yet
- `updatebot` - Pulls the latest code and restarts the bot (admin only)

## Slash Commands

- `/inventory @user` - Shows a user's inventory
- `/completion @user` - Shows a user's completion percentage
- `/remaining @user` - Shows what a user hasn't caught yet

New admin slash commands

- `/role add|remove|list|reset` - Manage bot-level roles. Owner-only.
- `/spawnrules probability <channel> <float>` - Set per-channel spawn probability (0-1). Use 0 to remove.
- `/spawnrules time <channel> <seconds>` - Set per-channel guaranteed spawn interval (seconds). Use 0 to remove.
- `/spawnrules list|remove` - List or remove rules for a channel or guild.
