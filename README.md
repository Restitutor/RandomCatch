# Math Catch Discord Bot

A Discord bot that allows users to catch math objects that randomly appear in designated channels.

## Project Structure

```
├── main.py    # Main entry point and Discord event handling
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

3. Run the bot, for that you can either run the start.sh file, or run the main.py file using uv (`uv run main.py`)

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
