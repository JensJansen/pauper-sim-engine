"""D1-D4: a game is a pure function of (decks, seed, chosen actions).

The action-space suite already depends on this: `support.fork` falls back to replaying a game from its seed when a state
cannot be deep-copied safely, and the training harness assumes a seed reproduces a game. Nothing proved it. Each test
compares per-decision DIGESTS of the full deep state fingerprint (not just the outcome), so a divergence is pinned to
the first decision at which the two games differ.

  D1  the same seed twice, in one process                         -> identical states at every decision
  D2  replaying the recorded actions (the fork-fallback path)      -> identical states at every decision
  D3  another game played in between (module-level caches)         -> identical states at every decision
  D4  the event log switched on                                    -> identical states (logging must not change the game)
"""
import os

import pytest

import game
from support import trace as T

GAMES = int(os.environ.get("DETERMINISM_GAMES", "24"))  # (pair, gi) samples; ~1.5 s each


def _samples():
    pairs = T.pool_pairs()
    step = max(1, len(pairs) // GAMES)
    return [(a, b, gi) for gi, (a, b) in enumerate(pairs[::step][:GAMES])]


SAMPLES = _samples()
IDS = [f"{a}-vs-{b}-g{gi}" for a, b, gi in SAMPLES]


def _assert_same(t1, t2, what):
    i = T.first_divergence(t1, t2)
    assert i is None, (f"{what}: games diverge at decision {i} "
                       f"(chosen {t1.chosen[i:i + 1]} vs {t2.chosen[i:i + 1]}; errors {t1.error!r} / {t2.error!r})")


@pytest.mark.parametrize("a,b,gi", SAMPLES, ids=IDS)
def test_d1_the_same_seed_plays_the_same_game(a, b, gi):
    _assert_same(T.run_game(a, b, gi), T.run_game(a, b, gi), "same seed, run twice")


@pytest.mark.parametrize("a,b,gi", SAMPLES, ids=IDS)
def test_d2_replaying_the_recorded_actions_reproduces_every_state(a, b, gi):
    original = T.run_game(a, b, gi)
    replay = T.run_game(a, b, gi, forced=original.chosen)
    assert len(replay.digests) == len(original.digests)
    _assert_same(T.Trace(digests=original.digests, error=original.error),
                 T.Trace(digests=replay.digests, error=replay.error), "forced replay")


@pytest.mark.parametrize("a,b,gi", SAMPLES[:8], ids=IDS[:8])
def test_d3_a_game_in_between_changes_nothing(a, b, gi):
    # The engine keeps per-sweep caches in module globals (drl_env._actions_mana, game.mana). A different game played in
    # between must leave no trace in the next one.
    first = T.run_game(a, b, gi)
    T.run_game("coverage_3", "coverage_4", gi + 7)
    _assert_same(first, T.run_game(a, b, gi), "after another game")


@pytest.mark.parametrize("a,b,gi", SAMPLES[:8], ids=IDS[:8])
def test_d4_turning_the_event_log_on_changes_nothing(a, b, gi, monkeypatch):
    # `_logged_pt` is the replay viewer's "last stats I logged" bookkeeping, only refreshed while logging: not game state.
    ignore = ("_logged_pt",)
    plain = T.run_game(a, b, gi, ignore_keys=ignore)
    real = game.new_multiplayer_game_state
    monkeypatch.setattr(game, "new_multiplayer_game_state",
                        lambda *args, **kw: real(*args, **{**kw, "event_log": []}))
    logged = T.run_game(a, b, gi, ignore_keys=ignore)
    _assert_same(plain, logged, "event log on")


def test_the_samples_cover_every_deck_and_end_in_real_games():
    decks = {d for a, b, _ in SAMPLES for d in (a, b)}
    assert len(decks) >= 4, decks
    t = T.run_game(*SAMPLES[0][:2], SAMPLES[0][2])
    assert t.error is None and len(t.digests) > 100
