"""Regression: a self-sacrificing mana source (Lotus Petal / Treasure) must not be tapped for mana while it is the only
fodder for the spell's own "sacrifice an artifact or creature" cost (Reckoner's Bargain, Fanatical Offering, Eviscerator's
Insight). Costs are paid together (601.2h), so such a cast cannot be finished; the engine used to let it start and then
crashed in `_sac_artifact_or_creature._on_chosen` (begin_choose_permanent completed with None). Found by the
action-space corpus (coverage_4 vs coverage_3, game 18); the production dumps in logs/sac_fizzle_diagnostics.jsonl are
the same shape (no fodder left, a stray floating pip)."""
import game
from drl_env import _actions_cast, _actions_mana
from game.cards import CardDef, CardType, EffectId
from game.state import GameState, Permanent

BARGAIN = "Reckoner's Bargain"  # {1}{B}, sacrifice an artifact or creature


def _state(*battlefield):
    state = GameState(on_the_play=True)
    state.phase = game.turn.Phase.MAIN1
    state.hand = [game.CARD_DEFS[BARGAIN]]
    state.battlefield = [Permanent(game.CARD_DEFS[n]) if isinstance(n, str) else n for n in battlefield]
    for p in state.battlefield:
        p.summoning_sick = False
    return state


def _creature():
    return Permanent(CardDef("Fodder", CardType.CREATURE, {"B": 1}, EffectId.FILLER, power=1, toughness=1))


def _cast_row(state):
    spec = game.EFFECT_REGISTRY[game.CARD_DEFS[BARGAIN].effect_id]["cast"]
    return (_actions_cast._cast_legal(BARGAIN, spec["extra_legal"], game.turn.Speed.SORCERY),
            _actions_cast._precast_choice_execute(BARGAIN, spec["resolve"]))


def test_cast_is_not_offered_when_it_needs_the_only_fodder_for_mana():
    # {1}{B}: one Swamp makes the B, the generic needs the Petal -- but the Petal is the only thing to sacrifice.
    state = _state("Swamp", "Lotus Petal")
    legal, _execute = _cast_row(state)
    assert not legal(state)


def test_cast_is_offered_when_another_permanent_can_be_the_fodder():
    state = _state("Swamp", "Lotus Petal", _creature())
    legal, _execute = _cast_row(state)
    assert legal(state)


def test_cast_is_offered_when_the_petal_is_not_needed_for_mana():
    state = _state("Swamp", "Swamp", "Lotus Petal")
    legal, _execute = _cast_row(state)
    assert legal(state)


def test_tapping_the_only_fodder_mid_payment_is_refused_but_other_sources_are_not():
    state = _state("Swamp", "Swamp", "Lotus Petal")
    _legal, execute = _cast_row(state)
    execute(state)
    assert state.pending_resolution["kind"] == "pay_cost"
    assert not _actions_mana._mana_ability_legal("Lotus Petal", "B")(state)
    assert _actions_mana._mana_ability_legal("Swamp", None)(state) or _actions_mana._mana_ability_legal("Swamp", "B")(state)


def test_with_a_second_fodder_the_petal_may_be_tapped_and_the_cast_finishes():
    creature = _creature()
    state = _state("Swamp", "Lotus Petal", creature)
    _legal, execute = _cast_row(state)
    execute(state)
    assert _actions_mana._mana_ability_legal("Lotus Petal", "B")(state)
    game.activate_mana_source(state, next(p for p in state.battlefield if p.card_def.name == "Lotus Petal"), "B")
    game.activate_mana_source(state, next(p for p in state.battlefield if p.card_def.name == "Swamp"))
    game.execute_pool_spend(state, "B")
    game.execute_pool_spend(state, "B")  # cost paid -> the sacrifice choice opens; the Petal is gone, so only `creature` is left
    pending = state.pending_resolution
    assert pending["kind"] == "choose_permanent"
    assert [p for p in state.battlefield if p.card_type == CardType.CREATURE] == [creature]


def test_two_petals_as_the_only_fodder_cannot_both_be_tapped():
    # {1}{B}: Swamp + Petal pays it, the second Petal stays as fodder. A cost that would need BOTH Petals is not offered.
    state = _state("Swamp", "Lotus Petal", "Lotus Petal")
    legal, execute = _cast_row(state)
    assert legal(state)
    execute(state)
    petal = next(p for p in state.battlefield if p.card_def.name == "Lotus Petal")
    game.activate_mana_source(state, petal, "B")
    assert not _actions_mana._mana_ability_legal("Lotus Petal", "B")(state)  # the last Petal is now the fodder
    assert game.payment_survives(state, game.available_mana_units(state))  # and the payment is still finishable
