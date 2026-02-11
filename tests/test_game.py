import random
import unittest
from unittest.mock import patch

from game import GameState
from models import SUMMON_COOLDOWN, Catch, FailedCatch, Item

ITEMS = {
    "cos": Item(
        key="cos", category="functions", names={"en": "cosine", "fr": "cosinus"},
    ),
    "sin": Item(key="sin", category="functions", names={"en": "sine", "fr": "sinus"}),
    "tan": Item(
        key="tan", category="functions", names={"en": "tangent", "fr": "tangente"},
    ),
}


class TestTryCatch(unittest.TestCase):
    def setUp(self):
        self.gs = GameState(ITEMS)

    def test_no_active_item(self):
        self.assertIsNone(self.gs.try_catch(1, "cosine"))

    def test_exact_match(self):
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "I see a cosine")
        self.assertIsInstance(result, Catch)
        self.assertEqual(result.item, ITEMS["cos"])
        self.assertEqual(result.matched_name, "cosine")

    def test_exact_clears_active(self):
        self.gs.active[1] = ITEMS["cos"]
        self.gs.try_catch(1, "cosine")
        self.assertNotIn(1, self.gs.active)

    def test_case_insensitive(self):
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "COSINE")
        self.assertIsNotNone(result)

    def test_fuzzy_close_typo(self):
        """'cosie' is close enough to 'cosine' (>85% similarity)."""
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "cosie")
        self.assertIsNotNone(result)
        self.assertEqual(result.matched_name, "cosine")

    def test_fuzzy_rejects_dissimilar(self):
        """'nine' must NOT fuzzy-match 'sine' (word ≤4 chars, skipped)."""
        self.gs.active[1] = ITEMS["sin"]
        result = self.gs.try_catch(1, "nine")
        self.assertIsNone(result)

    def test_fuzzy_skips_short_names(self):
        """Item name ≤4 chars is excluded from fuzzy matching candidates."""
        items = {"or_item": Item(key="or_item", category="symbols", names={"en": "or"})}
        gs = GameState(items)
        gs.active[1] = items["or_item"]
        # "roaming" is >4 chars but "or" (≤4) is excluded from fuzzy candidates
        result = gs.try_catch(1, "roaming")
        self.assertIsNone(result)

    def test_fuzzy_skips_short_words(self):
        """Text word ≤4 chars doesn't trigger fuzzy matching."""
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "cos")
        self.assertIsNone(result)

    def test_no_match(self):
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "hello world")
        self.assertIsNone(result)
        self.assertIn(1, self.gs.active)

    def test_failed_catch_feedback(self):
        """Saying 'catch' but with wrong name triggers FailedCatch."""
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "I'm trying to catch sine!")
        self.assertIsInstance(result, FailedCatch)
        self.assertIn(1, self.gs.active)  # Item remains active

    def test_catch_without_word_no_feedback(self):
        """Not saying 'catch' means no feedback."""
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "I think the answer is wrong")
        self.assertIsNone(result)
        self.assertIn(1, self.gs.active)


class TestDropRandom(unittest.TestCase):
    def setUp(self):
        self.gs = GameState(ITEMS)

    def test_sets_active(self):
        self.gs.drop_random(1)
        self.assertIn(1, self.gs.active)

    def test_returns_valid_item(self):
        item = self.gs.drop_random(1)
        self.assertIn(item.key, ITEMS)


class TestDropFavoringNew(unittest.TestCase):
    def setUp(self):
        self.gs = GameState(ITEMS)

    def test_sets_active(self):
        self.gs.drop_favoring_new(1, frozenset())
        self.assertIn(1, self.gs.active)

    def test_favors_new(self):
        """New (uncaught) items should be picked more than 50% of the time."""
        owned = frozenset(["cos"])
        new_count = 0
        trials = 300
        random.seed(42)
        for _ in range(trials):
            item = self.gs.drop_favoring_new(1, owned=owned)
            if item.key not in owned:
                new_count += 1
        self.assertGreater(new_count, trials * 0.5)

    def test_all_owned(self):
        owned = frozenset(ITEMS.keys())
        item = self.gs.drop_favoring_new(1, owned=owned)
        self.assertIn(item.key, ITEMS)

    def test_none_owned(self):
        item = self.gs.drop_favoring_new(1, owned=frozenset())
        self.assertIn(item.key, ITEMS)


class TestCooldowns(unittest.TestCase):
    def setUp(self):
        self.gs = GameState(ITEMS)

    @patch("game.time")
    def test_can_summon_initially(self, mock_time):
        mock_time.time.return_value = 10000.0
        self.assertTrue(self.gs.can_summon(1))

    @patch("game.time")
    def test_blocks_after_summon(self, mock_time):
        mock_time.time.return_value = 10000.0
        self.gs.record_summon(1)
        self.assertFalse(self.gs.can_summon(1))

    @patch("game.time")
    def test_remaining_positive(self, mock_time):
        mock_time.time.return_value = 10000.0
        self.gs.record_summon(1)
        mock_time.time.return_value = 10100.0
        self.assertGreater(self.gs.summon_cooldown_remaining(1), 0)

    @patch("game.time")
    def test_expires(self, mock_time):
        mock_time.time.return_value = 10000.0
        self.gs.record_summon(1)
        mock_time.time.return_value = 10000.0 + SUMMON_COOLDOWN + 1
        self.assertTrue(self.gs.can_summon(1))


if __name__ == "__main__":
    unittest.main()
