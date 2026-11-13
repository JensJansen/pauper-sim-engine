"""I1: every whole-state invariant holds at every decision of real games (`support.invariants`).

One test per invariant, over the whole corpus, so a failure names the rule that broke and shows the first positions that
broke it. A defect found by this suite and not yet fixed is a strict xfail (it XPASSes -> fails once fixed, then the marker
goes); none are open now -- README.md lists the fixed findings F-04..F-06.
"""
import pytest

from support.invariants import IDS as INVARIANTS

@pytest.mark.parametrize("inv", INVARIANTS)
def test_invariant_holds_at_every_decision(integrity_corpus, inv):
    n = integrity_corpus.violations.get(inv, 0)
    assert n == 0, f"{inv!r} failed at {n} decisions, first:\n" + "\n".join(str(s) for s in integrity_corpus.samples[inv])


def test_no_game_crashed(integrity_corpus):
    assert not integrity_corpus.errors, integrity_corpus.errors[:3]


def test_no_unknown_invariant_ids_fired(integrity_corpus):
    unknown = set(integrity_corpus.violations) - set(INVARIANTS)
    assert not unknown, f"an invariant fired that this file does not list: {unknown}"


# ---- coverage gate: the corpus must actually contain what the invariants talk about ---------------------------------
MIN_SEEN = {
    "decision": 100_000, "at_priority": 30_000, "stack_nonempty": 1_000, "attackers": 500, "blocked": 100,
    "pool_nonempty": 5_000, "graveyard_nonempty": 20_000, "exile_or_impulse": 100, "same_named_permanents": 5_000,
    "aura_attached": 500, "counters": 200, "damage_marked": 100, "token_on_battlefield": 1_000,
}


@pytest.mark.parametrize("situation,minimum", sorted(MIN_SEEN.items()))
def test_the_corpus_contains_the_situation(integrity_corpus, situation, minimum):
    assert integrity_corpus.seen[situation] >= minimum, (
        f"only {integrity_corpus.seen[situation]} decisions with {situation!r} (need {minimum}): the invariants that rely "
        f"on it were barely exercised")


def test_every_pending_kind_the_corpus_reaches_is_checked(integrity_corpus):
    kinds = {s for s in integrity_corpus.seen if s.startswith("pending:")}
    assert len(kinds) >= 25, sorted(kinds)
