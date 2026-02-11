TOKEN_FILE = "token"
DATABASE = "inventory.db"
DATA_FILE = "data.csv"

RANDOM_DROP_CHANCE = 0.0  # default per-message drop chance

ADMIN_IDS = {502141502038999041, 1168452148049231934, 459147358463197185}

with open(TOKEN_FILE) as f:
    TOKEN = f.read().strip()
