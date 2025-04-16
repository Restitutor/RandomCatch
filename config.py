#!/usr/bin/env python3
"""
Configuration file for Discord math catch bot.
Centralizes all configuration settings to avoid hard-coding values throughout the code.
"""

# File paths
TOKEN_FILE = "token"
DATABASE = "inventory.db"
DATA_FILE = "data.csv"

# Game configuration
RANDOM_DROP_TIME = 3600  # Seconds between random drops
RANDOM_DROP_CHANCE = 0.02  # 2% chance of random drop on message

# Discord configuration
ALLOWED_CHANNELS = (1211674089073279106,)
ADMIN_IDS = {502141502038999041, 1168452148049231934, 459147358463197185}

# Load token from file at import time
with open(TOKEN_FILE) as f:
    TOKEN = f.read().strip()
