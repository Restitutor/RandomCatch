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
├── token            # Discord bot token
└── inventory.db     # SQLite database for storing user inventories
```

## How to Run

1. Ensure you have the required dependencies installed:
   ```
   pip install -r requirements.txt
   ```

2. Make sure you have a valid Discord bot token in a file named `token`

3. Run the bot:
   ```
   python bot.py
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
