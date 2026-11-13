"""Engine-native agents: play any game with nothing but `game` and `drl_env` (no observation, no network).

A decision is the production action space the engine offers: the deck's fixed table rows (`drl_env.legal_action_mask`)
followed by one pointer slot per addressable object (`drl_env.action_bridge.pointer_identities`). `build_decision` is
the engine-side counterpart of the policy's `_build_decision` and produces the fields the suites read (`full_mask`,
`fixed_table`, `n_fixed`, `identities`), so a corpus run reads the same with either.

Policies:
  * `first_legal` / `FirstLegalAgent` -- the lowest-index legal action. Fully deterministic, for tests that need
    consistency. It is NOT guaranteed to make progress (a position where the first legal action is always a repeatable one
    never reaches the end of the turn), so always play it with a turn horizon.
  * `SeededRandomAgent` -- uniform over legal actions from its own `random.Random(seed)` (never global state), so a
    seed replays exactly. This is what the coverage corpora use.
"""
import random
from dataclasses import dataclass

import numpy as np

import drl_env
import game
from drl_env import action_bridge as AB

PREGAME_KINDS = ("mulligan_decision", "mulligan_bottom")


@dataclass
class Decision:
    full_mask: np.ndarray
    identities: list
    fixed_table: list
    n_fixed: int
    n_legal: int


def build_decision(state, seat, deck_ctx, horizon=None):
    """`deck_ctx` is the (vocab, fixed_table) shape `support.pool.build_pool` returns (vocab is always None here);
    `horizon` is accepted and ignored so call sites read like the policy's."""
    fixed_table = deck_ctx[1]
    identities = AB.pointer_identities(state, seat)
    fixed_mask = np.asarray(drl_env.legal_action_mask(state, fixed_table), dtype=bool)
    pointer_mask = AB.pointer_legal_mask(state, identities) if AB.any_pointer_legal(state) else [False] * len(identities)
    full_mask = np.concatenate([fixed_mask, np.asarray(pointer_mask, dtype=bool)])
    return Decision(full_mask, identities, fixed_table, len(fixed_table), int(full_mask.sum()))


def raise_all_false(state, seat):
    """An all-False mask: the engine reached a decision the action space cannot represent."""
    pend = state.pending_resolution
    pend_dump = {k: v for k, v in pend.items() if k != "on_complete"} if pend else None
    raise RuntimeError(
        f"all-False action mask for pending kind {pend['kind'] if pend else None!r} "
        f"(phase={state.phase} seat={seat} turn={state.turn_number} active_idx={state.active_idx} "
        f"turn_player={state.turn_player_idx})\n  pending_resolution={pend_dump!r}\n"
        f"  hand={[c.name for c in state.hand]}\n"
        f"  battlefield={[(p.card_def.name, p.tapped, dict(p.flags), p.summoning_sick) for p in state.battlefield]}\n"
        f"  mana_pool={dict(state.players[seat].mana_pool)}")


def executor_for(state, action_idx, fixed_table, identities):
    """The zero-arg callable that applies action_idx (a fixed row's execute closure, or a pointer pick)."""
    if action_idx < len(fixed_table):
        execute_fn = fixed_table[action_idx][2]
        return lambda state=state, execute_fn=execute_fn: execute_fn(state)
    chosen = identities[action_idx - len(fixed_table)]
    return lambda state=state, chosen=chosen: AB.execute_pointer_choice(state, chosen)


def is_pass(action_idx, fixed_table):
    return action_idx < len(fixed_table) and fixed_table[action_idx][0] == "Pass"


class RandomMulligan:
    """Uniform-random keep/mulligan (respecting the London cap) and uniform-random bottom choice, from `rng`."""

    def __init__(self, rng):
        self.rng = rng

    def decide(self, state):
        pend = state.pending_resolution
        if pend["kind"] == "mulligan_decision":
            if state.mulligans_taken < game.HAND_SIZE_LIMIT and self.rng.random() < 0.5:
                return lambda state=state: game.execute_mulligan_take(state)
            return lambda state=state: game.execute_mulligan_keep(state)
        name = self.rng.choice(game.bottom_options(state))
        return lambda state=state, name=name: game.execute_bottom_option(state, name)


class AlwaysKeep:
    """Keeps every opening hand (so mulligan_bottom is never reached)."""

    def decide(self, state):
        return lambda state=state: game.execute_mulligan_keep(state)


def first_legal(legal, dec, state, rng=None):
    return int(legal[0])


def uniform(legal, dec, state, rng):
    return int(rng.choice(list(legal)))


class _Agent:
    """Drives both seats: `choose_action(state)` is the callable `game.run_multiplayer_game` expects, picking for whichever
    seat holds the decision. `seats`: (deck name, deck name); `pool`: `support.pool.build_pool()`."""
    policy = None

    def __init__(self, seats, pool, mulligan, rng):
        self.seats, self.ctxs, self.mulligan, self.rng = seats, pool[2], mulligan, rng
        self.decisions = 0

    def choose_action(self, state):
        seat = state.active_idx
        pend = state.pending_resolution
        if pend is not None and pend["kind"] in PREGAME_KINDS:
            return self.mulligan.decide(state)
        dec = build_decision(state, seat, self.ctxs[self.seats[seat]])
        legal = np.flatnonzero(dec.full_mask)
        if legal.size == 0:
            raise_all_false(state, seat)
        i = type(self).policy(legal, dec, state, self.rng)
        self.decisions += 1
        if is_pass(i, dec.fixed_table):
            return None
        return executor_for(state, i, dec.fixed_table, dec.identities)


class FirstLegalAgent(_Agent):
    """Deterministic: keeps every hand, then always takes the lowest-index legal action."""
    policy = staticmethod(first_legal)

    def __init__(self, seats, pool):
        super().__init__(seats, pool, AlwaysKeep(), None)


class SeededRandomAgent(_Agent):
    """Deterministic given `seed`: random mulligans and uniformly random legal actions, all from rngs seeded from it."""
    policy = staticmethod(uniform)

    def __init__(self, seats, pool, seed):
        super().__init__(seats, pool, RandomMulligan(random.Random(seed)), random.Random(seed * 7_919 + 1))


def play_game(pool, deck_a, deck_b, agent, seed, starting_player=0, horizon=14, event_log=None):
    """One full game of `deck_a` (seat 0) vs `deck_b` (seat 1), seeded, driven by `agent` (built for the same two decks).
    Returns the final state."""
    decklists = pool[0]
    return game.run_multiplayer_game([decklists[deck_a], decklists[deck_b]], random.Random(seed), starting_player,
                                     agent.choose_action, horizon=horizon, combat_enabled=True, event_log=event_log)
