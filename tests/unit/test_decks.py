"""The fabricated coverage decks (tests/data/decks) must contain every implemented card at least once."""
import game
from support.pool import build_pool


def test_every_implemented_card_is_in_a_coverage_deck():
    decklists = build_pool()[0]
    in_decks = {name for dl in decklists.values() for name, _qty in dl}
    missing = sorted(set(game.CARD_DEFS) - in_decks)
    assert not missing, f"cards in no coverage deck (add them to tests/data/decks/*.txt): {missing}"
