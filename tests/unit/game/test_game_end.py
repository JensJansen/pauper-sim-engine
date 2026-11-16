"""The game ends the moment a life total reaches 0 -- no further decision is ever requested, no further stack item
resolves, no further phase runs.

AUTHORIZED SIMPLIFICATION (owner, 2026-11-16): real Magic ends the game at the next state-based-action check
(704.5a); here the game ends as soon as the effect that took a life total to 0 has finished resolving. The effect
in progress completes (so a single effect that takes BOTH players to 0 is a draw, 104.4a), then nothing else
happens. A draw is state.winner None with state.is_draw True (turn_won is set, as for any decided game)."""
import random

from game.cards import CardDef, CardType
from game.effects.stack import push_ability_to_stack, push_to_stack
from game.effects.win_check import _check_end_of_game, deal_damage_to_opponent, lose_life
from game.state import GameState, PlayerState
from game.turn import Phase, _run_priority_round_gen, new_multiplayer_game_state, run_turn

BURN = CardDef("Test Burn", CardType.INSTANT, None, None)


def _state(life0=20, life1=20):
    state = GameState(on_the_play=True, players=[PlayerState(True), PlayerState(False)])
    state.turn_player_idx = state.active_idx = 0
    state.players[0].life_total, state.players[1].life_total = life0, life1
    return state


def _drive(state, plan):
    """Runs one priority round, feeding `plan` (actions / None passes). Returns (decisions requested after turn_won was
    already set, whether the round ended on its own)."""
    late = 0
    gen = _run_priority_round_gen(state)
    try:
        next(gen)
        for step in plan:
            if state.turn_won is not None:
                late += 1
            gen.send(step)
    except StopIteration:
        return late, True
    return late, False


def test_lethal_action_ends_the_priority_round_at_once():
    state = _state(life1=3)
    late, ended = _drive(state, [lambda: deal_damage_to_opponent(state, 3), None, None, None])
    assert state.winner == 0 and state.turn_won is not None and not state.is_draw
    assert ended and late == 0, "the round kept asking for decisions after the opponent reached 0 life"
    assert state.active_idx == state.turn_player_idx


def test_lethal_stack_resolution_ends_the_round_and_resolves_nothing_further():
    state = _state(life1=3)
    resolved = []
    push_to_stack(state, BURN, lambda s, cd: resolved.append("under"))
    push_ability_to_stack(state, BURN, lambda s: deal_damage_to_opponent(s, 3))
    late, ended = _drive(state, [None, None, None, None, None, None])  # both pass -> top resolves -> game over
    assert state.winner == 0 and ended and late == 0
    assert resolved == [], "a stack item below the lethal one still resolved after the game was decided"
    assert len(state.stack) == 1


def test_the_final_effect_finishes_resolving_before_the_game_ends():
    state = _state(life1=3)
    steps = []

    def _lethal_then_more(s):
        deal_damage_to_opponent(s, 3)
        steps.append("rest of the same effect")

    push_ability_to_stack(state, BURN, _lethal_then_more)
    late, ended = _drive(state, [None, None, None, None])
    assert steps == ["rest of the same effect"]  # owner-approved: the effect in progress completes
    assert state.winner == 0 and ended and late == 0


def test_paying_life_to_zero_ends_the_round_and_the_opponent_wins():
    state = _state(life0=4)
    late, ended = _drive(state, [lambda: lose_life(state, 4, reason="cost"), None, None])
    assert state.winner == 1 and not state.is_draw and ended and late == 0


def test_no_decision_is_requested_after_lethal_in_a_full_turn():
    state = new_multiplayer_game_state([[("Mountain", 20)], [("Mountain", 20)]], 0, random.Random(0))
    state.players[1].life_total = 3
    fired = []
    asked_after_game_over = []

    def policy(st):
        if st.turn_won is not None:
            asked_after_game_over.append((st.phase, st.active_idx))
        if st.phase is Phase.MAIN1 and not fired and not st.stack:
            fired.append(1)
            return lambda: push_ability_to_stack(st, BURN, lambda s: deal_damage_to_opponent(s, 3))
        return None

    run_turn(state, policy)
    assert state.winner == 0 and fired
    assert asked_after_game_over == []
    assert state.phase is Phase.MAIN1, "the turn kept advancing through later phases after the game was over"


# ---- draws ------------------------------------------------------------------------------------------------------


def test_one_effect_taking_both_players_to_zero_is_a_draw():
    state = _state(life0=3, life1=3)

    def _both(s):
        deal_damage_to_opponent(s, 3)  # opponent first ...
        lose_life(s, 3, reason="cost")  # ... then the caster, inside the same effect

    push_ability_to_stack(state, BURN, _both)
    late, ended = _drive(state, [None, None, None, None])
    assert state.turn_won is not None and state.winner is None and state.is_draw
    assert ended and late == 0


def test_the_draw_does_not_depend_on_which_player_reached_zero_first():
    state = _state(life0=3, life1=3)

    def _both(s):
        lose_life(s, 3, reason="cost")  # the caster first (opponent would win right here) ...
        deal_damage_to_opponent(s, 3)  # ... then the opponent, same effect

    push_ability_to_stack(state, BURN, _both)
    late, ended = _drive(state, [None, None, None, None])
    assert state.winner is None and state.is_draw and ended and late == 0


def test_both_players_at_zero_is_a_draw_not_a_win_for_the_active_player():
    state = _state(life0=0, life1=0)
    _check_end_of_game(state)
    assert state.turn_won is not None and state.winner is None and state.is_draw


def test_a_decided_game_and_a_horizon_timeout_are_not_draws():
    state = _state(life1=1)
    assert not state.is_draw  # in progress
    deal_damage_to_opponent(state, 1)
    assert state.winner == 0 and not state.is_draw
    timeout = new_multiplayer_game_state([[("Mountain", 20)], [("Mountain", 20)]], 0, random.Random(0))
    assert timeout.turn_won is None and timeout.winner is None and not timeout.is_draw


# ---- deck-out after the game is decided -------------------------------------------------------------------------


def test_decking_out_after_a_lethal_effect_does_not_change_the_winner():
    state = new_multiplayer_game_state([[("Mountain", 20)], [("Mountain", 20)]], 0, random.Random(0))
    state.players[1].life_total = 3
    state.players[0].library = []  # the lethal effect's own follow-up draw would deck player 0 out
    fired = []

    def _lethal_then_draw(s):
        deal_damage_to_opponent(s, 3)
        s.players[0].draw(1)  # raises DeckedOut mid-effect

    def policy(st):
        if st.phase is Phase.MAIN1 and not fired and not st.stack:
            fired.append(1)
            return lambda: push_ability_to_stack(st, BURN, _lethal_then_draw)
        return None

    run_turn(state, policy)
    assert state.winner == 0 and not state.is_draw, "the deck-out overwrote an already-decided winner"
