# Math Catch Discord Bot

A Discord bot that allows users to catch mathematical objects that randomly appear in designated channels. Track your "MathDex" completion and compete on the leaderboard!

## Project Structure

```
RandomCatch/
├── main.py                 # Entry point (async bot runner)
├── config.py              # Configuration and environment variables
├── models.py              # Dataclass definitions (Item, Catch, SpawnRule, etc.)
├── game.py                # Game state and mechanics
├── items.py               # CSV loader for catchable items
├── db.py                  # SQLite database operations
├── utils.py               # Utility functions (JSON persistence, logging)
├── data.csv               # CSV of catchable math objects
├── cogs/
│   ├── catching.py        # Spawn logic and catch listener
│   ├── admin.py           # Spawn rules and role management
│   └── inventory.py       # Inventory and completion commands
├── tests/
│   ├── test_game.py
│   ├── test_models.py
│   ├── test_items.py
│   ├── test_utils.py
│   └── ...
├── spawn_rules.json       # Per-channel spawn configuration
├── roles.json             # Admin and owner role assignments
└── inventory.db           # SQLite database (auto-created)
```

## Installation

1. **Install Python 3.13+** and ensure `uv` is available

2. **Create `config.py`** with your Discord bot token:

   ```python
   TOKEN = "your-bot-token-here"
   TOKEN_FILE = "token"  # or set TOKEN above
   ADMIN_IDS = {12345678901234567}  # Your Discord user ID
   DATABASE = "inventory.db"
   DATA_FILE = "data.csv"
   RANDOM_DROP_CHANCE = 0.001  # 0.1% chance per message without spawn rules
   ```

3. **Run the bot:**
   ```bash
   uv run main.py
   ```

## Testing

Run the test suite:

```bash
python -m pytest tests/ -v
```

Tests that require optional dependencies (discord.py) are skipped if not installed.

## Features

### User Commands

**Hybrid Commands** (work as prefix or slash commands):

- `/summon` - Trigger a random item drop (1-hour cooldown)
- `/inventory [user] [category]` - View inventory (default: all items)
- `/completion [user]` - Show % completion of all items
- `/remaining [user]` - List uncaught items
- `/countobjects` - Total number of catchable items
- `/leaderboard` - Top 10 completion rankings

### Admin Commands

**Spawn Rules** (`/spawnrules` group):

- `/spawnrules probability <channel> <0-1>` - Set per-message spawn probability
- `/spawnrules time <channel> <1-604800>` - Set guaranteed spawn interval (seconds)
- `/spawnrules list [channel]` - Show spawn rules for this guild
- `/spawnrules status` - Show timer status and next spawn times
- `/spawnrules remove <channel>` - Delete all rules for a channel

**Role Management** (`/role` group):

- `/role add <owner|global_admin> <user>` - Grant role
- `/role remove <owner|global_admin> <user>` - Revoke role
- `/role list` - Show all role holders
- `/role reset` - Clear all roles (owner-only)

**Bot Management**:

- `/updatebot` - Pull latest code from git and restart (owner-only)

## Item Categories

Items are organized into categories:

- `numbers1-50` / `numbers51-100` - Numbers
- `sets` - Set theory
- `constants` - Mathematical constants
- `functions` - Common functions (sin, cos, log, etc.)
- `theorems` - Famous theorems
- `symbols` - Mathematical symbols
- `capitalgreek` / `smallgreek` - Greek letters
- `sequence` - Sequences

## How It Works

### Spawning

Items spawn in channels that have spawn rules configured via `/spawnrules`:

1. **Probability-based**: On each message, roll a probability to spawn
2. **Time-based**: Guaranteed spawn every N seconds
3. **Hybrid**: Both probability AND timer active simultaneously

### Catching

When an item is active in a channel, players catch it by saying its name (or a fuzzy match):

```
User: "I think sine is important"
Bot: "A new Math object dropped! `sin`. Catch it by saying its name!"
User: "sine"
Bot: "Caught sin -> sine"
```

Feedback is provided when you use the word "catch" but get the name wrong:

```
User: "Trying to catch... cosine?"
Bot: "That is not the right name.."
```

### Tracking

- **Inventory**: Tracks which items each user has caught and their counts
- **Leaderboard**: Top 10 users by total items caught
- **Categories**: Filter inventory by category (e.g., "show me all functions")

## Configuration

### Spawn Rules JSON Format

`spawn_rules.json`:

```json
{
  "rules": {
    "123456789": {
      "guild_id": 987654321,
      "probability": 0.5,
      "interval": 0
    },
    "234567890": {
      "guild_id": 987654321,
      "probability": 0.0,
      "interval": 1800
    }
  }
}
```

- **probability** (0.0, 1.0]: per-message spawn chance (0 = disabled)
- **interval** [1, 604800]: seconds between guaranteed spawns (0 = disabled)
- At least one must be > 0

### CSV Format

`data.csv`:

```csv
key,category,en,fr
sin,functions,sine,sinus
cos,functions,cosine,cosinus
```

- **key**: Unique identifier
- **category**: One of the categories above
- **en, fr, ...**: Names in different languages (columns auto-discovered)

Missing language values are skipped (e.g., blank `fr` cell means no French name).
