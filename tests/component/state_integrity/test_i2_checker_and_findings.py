"""I2: the invariant checker itself, and the open findings pinned deterministically.

A checker that never fires proves nothing, so each invariant gets a hand-built position that breaks exactly it. The F-06
test reproduces a corpus-found defect without depending on random play reaching it.
"""
import pytest

import game
from game.state import CardInstance, GameState, Permanent, PlayerState
from support import invariants as I


def _state(bf0=(), bf1=(), gy0=()):
    st = GameState(on_the_play=True, players=[PlayerState(True), PlayerState(False)])
    st.phase = game.turn.Phase.MAIN1
    for pl, names in ((st.players[0], bf0), (st.players[1], bf1)):
        for i, n in enumerate(names):
            p = Permanent(game.CARD_DEFS[n], iid=1000 + 10 * st.players.index(pl) + i)
            p.summoning_sick = False
            p.slot = 1 + sum(1 for q in pl.battlefield if q.card_def.name == n)
            pl.battlefield.append(p)
    for n in gy0:
        st.players[0].graveyard.append(CardInstance(game.CARD_DEFS[n], iid=900 + len(st.players[0].graveyard)))
    return st


def _ids(state, base=None):
    return {inv for inv, _msg in I.check(state, base or I.baseline(state))}


def test_a_clean_position_has_no_violations():
    assert _ids(_state(["Mountain", "Kitchen Imp"], ["Island"])) == set()


def _damaged_creature():
    st = _state(["Kitchen Imp"])
    st.players[0].battlefield[0].damage_marked = 99
    return st


def _orphaned_aura():
    st = _state(["Mountain", "Rancor"])
    st.players[0].battlefield[1].flags["enchanting"] = Permanent(game.CARD_DEFS["Kitchen Imp"])  # not on any battlefield
    return st


def _shared_permanent():
    st = _state(["Mountain"])
    st.players[1].battlefield.append(st.players[0].battlefield[0])
    return st


def _duplicate_slot():
    st = _state(["Mountain", "Mountain"])
    st.players[0].battlefield[1].slot = 1
    return st


def _stray_attacker():
    st = _state(["Kitchen Imp"])
    st.players[0].attackers = [Permanent(game.CARD_DEFS["Kitchen Imp"])]
    return st


PLANTED = {
    "idx": lambda: (lambda st: (setattr(st, "active_idx", 5), st)[1])(_state()),
    "pool": lambda: (lambda st: (st.players[0].mana_pool.update({"R": -1}), st)[1])(_state()),
    "counter": lambda: (lambda st: (setattr(st.players[0], "lands_played_this_turn", -1), st)[1])(_state()),
    "casting_depth": lambda: (lambda st: (setattr(st, "casting_depth", 1), st)[1])(_state()),
    "stack": lambda: (lambda st: (st.stack.append({"card_def": game.CARD_DEFS["Mountain"], "controller": 7, "is_spell": True,
                                                    "reserves_hand_card": True}), st)[1])(_state()),
    "perm": lambda: (lambda st: (setattr(st.players[0].battlefield[0], "damage_marked", -1), st)[1])(_state(["Kitchen Imp"])),
    "sba": _damaged_creature,
    "aura": _orphaned_aura,
    "zones": _shared_permanent,
    "slots": _duplicate_slot,
    "combat": _stray_attacker,
}


@pytest.mark.parametrize("inv", sorted(PLANTED))
def test_the_checker_fires_on_a_planted_violation(inv):
    assert inv in _ids(PLANTED[inv]()), f"invariant {inv!r} did not notice its planted violation"


def test_conservation_fires_on_a_duplicated_card():
    st = _state(["Mountain"])
    base = I.baseline(st)
    st.players[0].graveyard.append(CardInstance(game.CARD_DEFS["Mountain"], iid=5))  # a second Mountain from nowhere
    assert "conservation" in _ids(st, base)


def test_every_invariant_id_the_corpus_test_lists_can_be_planted():
    assert set(I.IDS) <= set(PLANTED) | {"conservation"}


def test_maelstrom_colossus_is_not_in_the_graveyard_once_it_has_resolved():
    colossus = game.CARD_DEFS["Maelstrom Colossus"]
    st = _state(["Mountain"])
    base = I.baseline(st)
    base[0]["Maelstrom Colossus"] = 1
    base[0]["Mountain"] = 2  # the one in play plus the one in the library
    st.resolving_card = colossus
    st.players[0].library = [game.CARD_DEFS["Mountain"]]  # a whiff: Cascade finds no nonland card, so it just enters
    game.catalog.colorless_cards.cast_maelstrom_colossus(st, colossus)
    assert "conservation" not in _ids(st, base)
