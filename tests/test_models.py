import unittest

import pytest

from models import (
    HybridSpawn,
    IntervalSpawn,
    Item,
    ProbabilitySpawn,
    SpawnRule,
)


class TestItemMatch(unittest.TestCase):
    def setUp(self) -> None:
        self.item = Item(
            key="sin", category="functions", names={"en": "sine", "fr": "sinus"},
        )

    def test_exact_english(self) -> None:
        assert self.item.match("sine") == "sine"

    def test_exact_french(self) -> None:
        assert self.item.match("sinus") == "sinus"

    def test_case_insensitive(self) -> None:
        assert self.item.match("SINE") == "sine"

    def test_substring(self) -> None:
        assert self.item.match("I said sine!") == "sine"

    def test_no_match(self) -> None:
        assert self.item.match("hello") is None

    def test_empty_text(self) -> None:
        assert self.item.match("") is None

    def test_short_name_substring(self) -> None:
        """Short names like 'or' match as substrings — the 'sum in summon' problem."""
        item = Item(key="or_item", category="symbols", names={"en": "or"})
        assert item.match("inventory") == "or"


class TestProbabilitySpawn(unittest.TestCase):
    def test_valid(self) -> None:
        s = ProbabilitySpawn(probability=0.5)
        assert s.probability == 0.5

    def test_max(self) -> None:
        s = ProbabilitySpawn(probability=1.0)
        assert s.probability == 1.0

    def test_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            ProbabilitySpawn(probability=0.0)

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            ProbabilitySpawn(probability=-0.1)

    def test_over_one_rejected(self) -> None:
        with pytest.raises(ValueError):
            ProbabilitySpawn(probability=1.1)


class TestIntervalSpawn(unittest.TestCase):
    def test_valid(self) -> None:
        s = IntervalSpawn(interval=60)
        assert s.interval == 60

    def test_min(self) -> None:
        s = IntervalSpawn(interval=1)
        assert s.interval == 1

    def test_max(self) -> None:
        s = IntervalSpawn(interval=604800)
        assert s.interval == 604800

    def test_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            IntervalSpawn(interval=0)

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            IntervalSpawn(interval=-1)

    def test_over_max_rejected(self) -> None:
        with pytest.raises(ValueError):
            IntervalSpawn(interval=604801)


class TestHybridSpawn(unittest.TestCase):
    def test_valid(self) -> None:
        s = HybridSpawn(probability=0.5, interval=60)
        assert s.probability == 0.5
        assert s.interval == 60

    def test_bad_probability(self) -> None:
        with pytest.raises(ValueError):
            HybridSpawn(probability=0.0, interval=60)

    def test_bad_interval(self) -> None:
        with pytest.raises(ValueError):
            HybridSpawn(probability=0.5, interval=0)


class TestSpawnRule(unittest.TestCase):
    def test_with_probability(self) -> None:
        rule = SpawnRule(
            channel_id=1, guild_id=2, mode=ProbabilitySpawn(probability=0.5),
        )
        assert isinstance(rule.mode, ProbabilitySpawn)

    def test_with_interval(self) -> None:
        rule = SpawnRule(channel_id=1, guild_id=2, mode=IntervalSpawn(interval=1800))
        assert isinstance(rule.mode, IntervalSpawn)

    def test_with_hybrid(self) -> None:
        rule = SpawnRule(
            channel_id=1,
            guild_id=2,
            mode=HybridSpawn(probability=0.5, interval=1800),
        )
        assert isinstance(rule.mode, HybridSpawn)


if __name__ == "__main__":
    unittest.main()
