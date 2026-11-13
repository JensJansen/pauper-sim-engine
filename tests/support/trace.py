"""Run one seeded game and return a comparable record of everything observable about it.

`run_game(a, b, gi, pi)` plays the game exactly as `support.action_corpus.play_one` does (same seeds, same random-legal
policy) and returns a `Trace`: the action index chosen at every decision, and a digest of the full deep state
fingerprint (`support.fingerprint.state_fingerprint`) taken at every decision BEFORE the action runs. Two runs are the
same game iff their traces are equal; the first differing decision is where they diverged.

`pool_pairs()` lists the ordered deck pairs in the order the corpus indexes them (`pi` seeds the game, so a pair must be
paired with its own index)."""
import hashlib
import random
from dataclasses import dataclass, field

from support import action_corpus as AC
from support.fingerprint import state_fingerprint
from support.pool import build_pool


@dataclass
class Trace:
    chosen: list = field(default_factory=list)       # full-mask index chosen at each non-pregame decision
    digests: list = field(default_factory=list)      # sha256 of the state fingerprint at each of those decisions
    error: str = None                                # repr of an exception that ended the game, else None


def digest(state, with_log_length=False, ignore_keys=()):
    fp, log_len = state_fingerprint(state, ignore_keys)
    payload = repr((fp, log_len)) if with_log_length else repr(fp)
    return hashlib.sha256(payload.encode()).hexdigest()


def pool_pairs():
    names = sorted(build_pool()[0])
    return [(a, b) for a in names for b in names]


def run_game(a, b, gi=0, pi=None, seed=0, horizon=AC.HORIZON, forced=None, stop_at=None, with_log_length=False,
             ignore_keys=()):
    """Play (a, b) game `gi`. `pi` defaults to the pair's index in pool_pairs() (what the corpus would use). `forced`:
    replay these chosen indices instead of sampling (the replay-fork path)."""
    pool = build_pool()
    if pi is None:
        pi = pool_pairs().index((a, b))
    game_id = AC.Game(a, b, gi, pi, seed, pool)
    trace = Trace()

    def on_decision(state, seat, deck, dec, legal, ctxs, tables):
        trace.digests.append(digest(state, with_log_length, ignore_keys))

    def policy(legal, dec, state, rng):
        i = AC.uniform_policy(legal, dec, state, rng)
        trace.chosen.append(i)
        return i

    prev, AC.CURRENT = AC.CURRENT, game_id
    try:
        AC.play_one(game_id, on_decision, policy=policy, horizon=horizon, forced=forced, stop_at=stop_at)
    except Exception as e:  # noqa: BLE001 -- a crash is part of what the game did; the caller compares it
        trace.error = repr(e)[:300]
    finally:
        AC.CURRENT = prev
    return trace


def first_divergence(t1, t2):
    """Index of the first decision at which two traces differ (state digest or chosen action), or None if identical."""
    for i, (x, y) in enumerate(zip(t1.digests, t2.digests)):
        if x != y:
            return i
    for i, (x, y) in enumerate(zip(t1.chosen, t2.chosen)):
        if x != y:
            return i
    if len(t1.digests) != len(t2.digests) or t1.error != t2.error:
        return min(len(t1.digests), len(t2.digests))
    return None
