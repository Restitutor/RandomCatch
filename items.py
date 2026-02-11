import csv
from typing import get_args

from models import Item, ItemCategory, ItemKey

VALID_CATEGORIES: frozenset[str] = frozenset(get_args(ItemCategory))


def load_items(path: str) -> dict[ItemKey, Item]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        langs = [col for col in reader.fieldnames if col not in ("key", "category")]
        items: dict[ItemKey, Item] = {}
        for row in reader:
            cat = row["category"]
            if cat not in VALID_CATEGORIES:
                raise ValueError(f"Invalid category {cat!r} for item {row['key']!r}")
            items[row["key"]] = Item(
                key=row["key"],
                category=cat,
                names={la: row[la] for la in langs if row.get(la, "").strip()},
            )
        return items
