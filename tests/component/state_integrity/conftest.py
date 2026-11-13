"""Fixtures for the state-integrity suite. The corpus is the same real self-play the action-space suite uses (every ordered
deck pair, uniform-random legal actions, `support.action_corpus.play_games`); `support.invariants.check` runs on the LIVE
state at every decision. Knob: INTEGRITY_GAMES (games per ordered pair, default 3; scaled like the action-space corpus)."""
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import pytest

import game

from support import action_corpus as AC
from support import invariants as I
from support.fixtures import _cwd_in_src  # noqa: F401
from support.paths import SRC

MAX_SAMPLES = 5


@dataclass
class IntegrityCorpus:
    decisions: int = 0
    games: int = 0
    errors: list = field(default_factory=list)
    violations: Counter = field(default_factory=Counter)          # invariant id -> number of decisions it failed at
    samples: dict = field(default_factory=lambda: defaultdict(list))  # invariant id -> first few (deck pair, game, decision, message)
    seen: Counter = field(default_factory=Counter)                # coverage: situation -> decisions it was present at


def _situations(state):
    """Which of the situations the invariants talk about this position contains (the coverage gate counts them)."""
    out = ["decision"]
    if state.pending_resolution is None and state.casting_depth == 0 and state.mana_subdecision is None:
        out.append("at_priority")
    if state.stack:
        out.append("stack_nonempty")
    if state.pending_resolution is not None:
        out.append("pending:" + state.pending_resolution["kind"])
    for pl in state.players:
        if pl.attackers:
            out.append("attackers")
        if pl.blocked_by:
            out.append("blocked")
        if pl.mana_pool:
            out.append("pool_nonempty")
        if pl.graveyard:
            out.append("graveyard_nonempty")
        if pl.exile or pl.impulse:
            out.append("exile_or_impulse")
        names = Counter(p.card_def.name for p in pl.battlefield)
        if any(k > 1 for k in names.values()):
            out.append("same_named_permanents")
        if any(p.flags.get("enchanting") is not None for p in pl.battlefield):
            out.append("aura_attached")
        if any(p.counters for p in pl.battlefield):
            out.append("counters")
        if any(p.damage_marked for p in pl.battlefield):
            out.append("damage_marked")
        if any(p.card_def.name not in game.CARD_DEFS for p in pl.battlefield):
            out.append("token_on_battlefield")
    return set(out)


def build_integrity_corpus(games_per_pair=3):
    corpus = IntegrityCorpus()
    baselines = {}

    def on_decision(state, seat, deck, dec, legal, ctxs, tables):
        g = AC.CURRENT
        key = (g.a, g.b, g.gi, g.pi)
        if key not in baselines:
            baselines[key] = I.baseline(state)
        corpus.decisions += 1
        corpus.seen.update(_situations(state))
        for inv, msg in I.check(state, baselines[key]):
            corpus.violations[inv] += 1
            if len(corpus.samples[inv]) < MAX_SAMPLES:
                corpus.samples[inv].append((f"{g.a} vs {g.b}", g.gi, g.count, msg))

    corpus.games, corpus.errors = AC.play_games(on_decision, games_per_pair=games_per_pair)
    return corpus


@pytest.fixture(scope="session")
def integrity_corpus():
    prev = os.getcwd()
    os.chdir(SRC)
    try:
        return build_integrity_corpus(int(os.environ.get("INTEGRITY_GAMES", "3")))
    finally:
        os.chdir(prev)
