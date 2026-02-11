import unittest

from models import (
    HybridSpawn,
    IntervalSpawn,
    Item,
    ProbabilitySpawn,
    SpawnRule,
)


class TestItemMatch(unittest.TestCase):
    def setUp(self):
        self.item = Item(
            key="sin", category="functions", names={"en": "sine", "fr": "sinus"},
        )

    def test_exact_english(self):
        self.assertEqual(self.item.match("sine"), "sine")

    def test_exact_french(self):
        self.assertEqual(self.item.match("sinus"), "sinus")

    def test_case_insensitive(self):
        self.assertEqual(self.item.match("SINE"), "sine")

    def test_substring(self):
        self.assertEqual(self.item.match("I said sine!"), "sine")

    def test_no_match(self):
        self.assertIsNone(self.item.match("hello"))

    def test_empty_text(self):
        self.assertIsNone(self.item.match(""))

    def test_short_name_substring(self):
        """Short names like 'or' match as substrings — the 'sum in summon' problem."""
        item = Item(key="or_item", category="symbols", names={"en": "or"})
        self.assertEqual(item.match("inventory"), "or")


class TestProbabilitySpawn(unittest.TestCase):
    def test_valid(self):
        s = ProbabilitySpawn(probability=0.5)
        self.assertEqual(s.probability, 0.5)

    def test_max(self):
        s = ProbabilitySpawn(probability=1.0)
        self.assertEqual(s.probability, 1.0)

    def test_zero_rejected(self):
        with self.assertRaises(ValueError):
            ProbabilitySpawn(probability=0.0)

    def test_negative_rejected(self):
        with self.assertRaises(ValueError):
            ProbabilitySpawn(probability=-0.1)

    def test_over_one_rejected(self):
        with self.assertRaises(ValueError):
            ProbabilitySpawn(probability=1.1)


class TestIntervalSpawn(unittest.TestCase):
    def test_valid(self):
        s = IntervalSpawn(interval=60)
        self.assertEqual(s.interval, 60)

    def test_min(self):
        s = IntervalSpawn(interval=1)
        self.assertEqual(s.interval, 1)

    def test_max(self):
        s = IntervalSpawn(interval=604800)
        self.assertEqual(s.interval, 604800)

    def test_zero_rejected(self):
        with self.assertRaises(ValueError):
            IntervalSpawn(interval=0)

    def test_negative_rejected(self):
        with self.assertRaises(ValueError):
            IntervalSpawn(interval=-1)

    def test_over_max_rejected(self):
        with self.assertRaises(ValueError):
            IntervalSpawn(interval=604801)


class TestHybridSpawn(unittest.TestCase):
    def test_valid(self):
        s = HybridSpawn(probability=0.5, interval=60)
        self.assertEqual(s.probability, 0.5)
        self.assertEqual(s.interval, 60)

    def test_bad_probability(self):
        with self.assertRaises(ValueError):
            HybridSpawn(probability=0.0, interval=60)

    def test_bad_interval(self):
        with self.assertRaises(ValueError):
            HybridSpawn(probability=0.5, interval=0)


class TestSpawnRule(unittest.TestCase):
    def test_with_probability(self):
        rule = SpawnRule(
            channel_id=1, guild_id=2, mode=ProbabilitySpawn(probability=0.5),
        )
        self.assertIsInstance(rule.mode, ProbabilitySpawn)

    def test_with_interval(self):
        rule = SpawnRule(channel_id=1, guild_id=2, mode=IntervalSpawn(interval=1800))
        self.assertIsInstance(rule.mode, IntervalSpawn)

    def test_with_hybrid(self):
        rule = SpawnRule(
            channel_id=1,
            guild_id=2,
            mode=HybridSpawn(probability=0.5, interval=1800),
        )
        self.assertIsInstance(rule.mode, HybridSpawn)


if __name__ == "__main__":
    unittest.main()
