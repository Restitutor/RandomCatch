from dataclasses import dataclass
from typing import Literal

type UserId = int
type ChannelId = int
type GuildId = int
type ItemKey = str
type Lang = str

SUMMON_COOLDOWN = 3600  # seconds

ItemCategory = Literal[
    "numbers1-50",
    "numbers51-100",
    "sets",
    "constants",
    "functions",
    "theorems",
    "symbols",
    "capitalgreek",
    "smallgreek",
    "sequence",
]


@dataclass(frozen=True, slots=True)
class Item:
    key: ItemKey
    category: ItemCategory
    names: dict[Lang, str]  # {"en": "sine", "fr": "sinus"}

    def match(self, text: str) -> str | None:
        """Exact substring match against any name (case-insensitive)."""
        text_lower = text.lower()
        return next((n for n in self.names.values() if n.lower() in text_lower), None)


@dataclass(frozen=True, slots=True)
class Catch:
    item: Item
    matched_name: str


@dataclass(frozen=True, slots=True)
class FailedCatch:
    """Player attempted to catch but used wrong name."""


@dataclass(frozen=True, slots=True)
class ProbabilitySpawn:
    """Per-message random spawn."""

    probability: float

    def __post_init__(self) -> None:
        if not (0.0 < self.probability <= 1.0):
            raise ValueError(
                f"Probability must be in (0.0, 1.0], got {self.probability}",
            )


@dataclass(frozen=True, slots=True)
class IntervalSpawn:
    """Fixed-interval timed spawn."""

    interval: int  # seconds

    def __post_init__(self) -> None:
        if not (1 <= self.interval <= 604800):
            raise ValueError(f"Interval must be in [1, 604800], got {self.interval}")


@dataclass(frozen=True, slots=True)
class HybridSpawn:
    """Both probability AND interval."""

    probability: float
    interval: int

    def __post_init__(self) -> None:
        if not (0.0 < self.probability <= 1.0):
            raise ValueError(
                f"Probability must be in (0.0, 1.0], got {self.probability}",
            )
        if not (1 <= self.interval <= 604800):
            raise ValueError(f"Interval must be in [1, 604800], got {self.interval}")


type SpawnMode = ProbabilitySpawn | IntervalSpawn | HybridSpawn


@dataclass(frozen=True, slots=True)
class SpawnRule:
    channel_id: ChannelId
    guild_id: GuildId
    mode: SpawnMode
