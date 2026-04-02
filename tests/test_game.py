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
    def setUp(self) -> None:
        self.gs = GameState(ITEMS)

    def test_no_active_item(self) -> None:
        assert self.gs.try_catch(1, "cosine") is None

    def test_exact_match(self) -> None:
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "I see a cosine")
        assert isinstance(result, Catch)
        assert result.item == ITEMS["cos"]
        assert result.matched_name == "cosine"

    def test_exact_clears_active(self) -> None:
        self.gs.active[1] = ITEMS["cos"]
        self.gs.try_catch(1, "cosine")
        assert 1 not in self.gs.active

    def test_case_insensitive(self) -> None:
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "COSINE")
        assert result is not None

    def test_fuzzy_close_typo(self) -> None:
        """'cosie' is close enough to 'cosine' (>85% similarity)."""
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "cosie")
        assert result is not None
        assert result.matched_name == "cosine"

    def test_fuzzy_rejects_dissimilar(self) -> None:
        """'nine' must NOT fuzzy-match 'sine' (word ≤4 chars, skipped)."""
        self.gs.active[1] = ITEMS["sin"]
        result = self.gs.try_catch(1, "nine")
        assert result is None

    def test_fuzzy_skips_short_names(self) -> None:
        """Item name ≤4 chars is excluded from fuzzy matching candidates."""
        items = {"or_item": Item(key="or_item", category="symbols", names={"en": "or"})}
        gs = GameState(items)
        gs.active[1] = items["or_item"]
        # "roaming" is >4 chars but "or" (≤4) is excluded from fuzzy candidates
        result = gs.try_catch(1, "roaming")
        assert result is None

    def test_fuzzy_skips_short_words(self) -> None:
        """Text word ≤4 chars doesn't trigger fuzzy matching."""
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "cos")
        assert result is None

    def test_no_match(self) -> None:
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "hello world")
        assert result is None
        assert 1 in self.gs.active

    def test_failed_catch_feedback(self) -> None:
        """Saying 'catch' but with wrong name triggers FailedCatch."""
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "I'm trying to catch sine!")
        assert isinstance(result, FailedCatch)
        assert 1 in self.gs.active  # Item remains active

    def test_catch_without_word_no_feedback(self) -> None:
        """Not saying 'catch' means no feedback."""
        self.gs.active[1] = ITEMS["cos"]
        result = self.gs.try_catch(1, "I think the answer is wrong")
        assert result is None
        assert 1 in self.gs.active


class TestDropRandom(unittest.TestCase):
    def setUp(self) -> None:
        self.gs = GameState(ITEMS)

    def test_sets_active(self) -> None:
        self.gs.drop_random(1)
        assert 1 in self.gs.active

    def test_returns_valid_item(self) -> None:
        item = self.gs.drop_random(1)
        assert item.key in ITEMS


class TestDropFavoringNew(unittest.TestCase):
    def setUp(self) -> None:
        self.gs = GameState(ITEMS)

    def test_sets_active(self) -> None:
        self.gs.drop_favoring_new(1, frozenset())
        assert 1 in self.gs.active

    def test_favors_new(self) -> None:
        """New (uncaught) items should be picked more than 50% of the time."""
        owned = frozenset(["cos"])
        new_count = 0
        trials = 300
        random.seed(42)
        for _ in range(trials):
            item = self.gs.drop_favoring_new(1, owned=owned)
            if item.key not in owned:
                new_count += 1
        assert new_count > trials * 0.5

    def test_all_owned(self) -> None:
        owned = frozenset(ITEMS.keys())
        item = self.gs.drop_favoring_new(1, owned=owned)
        assert item.key in ITEMS

    def test_none_owned(self) -> None:
        item = self.gs.drop_favoring_new(1, owned=frozenset())
        assert item.key in ITEMS


class TestCooldowns(unittest.TestCase):
    def setUp(self) -> None:
        self.gs = GameState(ITEMS)

    @patch("game.time")
    def test_can_summon_initially(self, mock_time) -> None:
        mock_time.time.return_value = 10000.0
        assert self.gs.can_summon(1)

    @patch("game.time")
    def test_blocks_after_summon(self, mock_time) -> None:
        mock_time.time.return_value = 10000.0
        self.gs.record_summon(1)
        assert not self.gs.can_summon(1)

    @patch("game.time")
    def test_remaining_positive(self, mock_time) -> None:
        mock_time.time.return_value = 10000.0
        self.gs.record_summon(1)
        mock_time.time.return_value = 10100.0
        assert self.gs.summon_cooldown_remaining(1) > 0

    @patch("game.time")
    def test_expires(self, mock_time) -> None:
        mock_time.time.return_value = 10000.0
        self.gs.record_summon(1)
        mock_time.time.return_value = 10000.0 + SUMMON_COOLDOWN + 1
        assert self.gs.can_summon(1)


if __name__ == "__main__":
    unittest.main()
