"""Shared infrastructure for the drl_env action-table modules: the
no-pending-resolution gate sentinel (used by _actions_cast,
_actions_cast_altzone, _actions_combat, _actions_resolution) and
_hand_count_available, shared by _actions_cast and _actions_cast_altzone.
Lives here rather than in either of them to avoid a cast <-> cast_altzone
import cycle. Also `_begin_cast_payment`, the one place a cast opens its mana payment (cast, precast-choice and
flashback paths all share it)."""
import itertools

import game

_GATE_NO_PENDING = object()  # marks a legal() closure gated on state.pending_resolution is None


def _hand_count_available(state, name):
    """Count of `name` currently in state.hand. A cast spell leaves hand
    immediately (push_to_stack removes it), so this doubles as the
    re-cast guard."""
    return sum(1 for c in state.hand if c.name == name)


def _flag_signature(value):
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted(repr(v) for v in value)))
    return ("obj", id(value))


def copy_signature(state, permanent):
    """Everything that can make two same-named permanents NOT interchangeable for an action: their own runtime state
    (tapped, summoning sickness, counters, damage, type override, flags) and the Auras attached to them -- on EITHER
    battlefield, since an Aura may enchant the other player's permanent. Two copies with equal signatures are the same
    choice (rules 602.2/605.3: the player chooses which permanent to tap or activate, so when the choice cannot matter
    it is not asked)."""
    auras = tuple(sorted(
        (a.card_def.name, tuple(sorted((k, _flag_signature(v)) for k, v in a.flags.items() if k not in ("enchanting", "_logged_pt"))))
        for pl in state.players for a in pl.battlefield if a.flags.get("enchanting") is permanent))
    return (
        permanent.card_def.name, permanent.tapped, permanent.summoning_sick, permanent.damage_marked,
        tuple(sorted(permanent.counters.items())), permanent.type_override,
        tuple(sorted((k, _flag_signature(v)) for k, v in permanent.flags.items() if k != "_logged_pt")),
        permanent.temp_power, permanent.temp_toughness, tuple(sorted(permanent.temp_keywords)), auras,
    )


def distinct_copies(state, permanents):
    """One representative per class of interchangeable permanents (see copy_signature), in the given order."""
    seen, out = set(), []
    for p in permanents:
        sig = copy_signature(state, p)
        if sig not in seen:
            seen.add(sig)
            out.append(p)
    return out


def taps_away(state, permanent):
    """Does activating `permanent`'s own mana ability remove it from the battlefield? (game.mana's registry predicate:
    Lotus Petal / Treasure sacrifice themselves, Wall of Roots can die to its own counter.)"""
    return game.mana._mana_tap_removes_self(state, permanent)


def cast_extra_legal(name, key="cast"):
    """The non-mana precondition of casting `name` (its registry `extra_legal`; for key="flashback" the ability's `legal`),
    or None. Looked up at cast time, not captured by the row's closures, so the action table's row structure is unchanged."""
    spec = game.EFFECT_REGISTRY.get(game.CARD_DEFS[name].effect_id, {}).get(key) or {}
    return spec.get("legal" if key == "flashback" else "extra_legal")


def _begin_cast_payment(state, cost, on_complete, extra_legal):
    """game.begin_pay_cost for a cast, plus the spell's own non-mana precondition (its registry `extra_legal`, e.g. "you
    control something to sacrifice") recorded on the open payment as pending["extra_legal"], so every later tap is judged
    by `unusable_for_extra_cost` (601.2h: all costs are paid together, so the cast cannot be finished without it)."""
    game.begin_pay_cost(state, cost, on_complete=on_complete)
    pending = state.pending_resolution
    if extra_legal is not None and pending is not None and pending["kind"] == "pay_cost" and pending["on_complete"] is on_complete:
        pending["extra_legal"] = extra_legal


def extra_cost_holds_without(state, extra_legal, gone):
    """Would `extra_legal(state)` still hold with the permanents `gone` off the battlefield? Pure (they are put back)."""
    battlefield = state.battlefield
    lifted = [(battlefield.index(p), p) for p in gone]
    for _at, p in lifted:
        battlefield.remove(p)
    try:
        return bool(extra_legal(state))
    finally:
        for at, p in sorted(lifted, key=lambda t: t[0]):
            battlefield.insert(at, p)


def unusable_for_extra_cost(state, extra_legal, gone=()):
    """The mana sources that cannot ALL be tapped for mana without breaking `extra_legal`: a source that is sacrificed by
    being tapped (Lotus Petal, Treasure: taps_away) may be the only fodder for Reckoner's Bargain.
    Returns every way to choose which of the other such sources to leave alone, as lists of permanents that must NOT be
    tapped -- one list per set `T` of them that may be consumed while `extra_legal` still holds with `gone` + T off the
    battlefield. [[]] (no restriction) when there is no precondition or no such source. `gone`: sources the caller is
    consuming right now.
    # ponytail: subsets of removable sources, capped at 8 sources; a game never holds more than a few Petals/Treasures."""
    if extra_legal is None:
        return [[]]
    removable = [p for p in state.battlefield
                 if p not in gone and game.tappable_for_mana(state, p) and taps_away(state, p)]
    if not removable and not gone:
        return [[]]
    removable = removable[:8]
    out = []
    for k in range(len(removable), -1, -1):
        for consumed in itertools.combinations(removable, k):
            if extra_cost_holds_without(state, extra_legal, list(gone) + list(consumed)):
                out.append([p for p in removable if p not in consumed])
    return out


def payable_keeping_extra_cost(state, cost, extra_legal):
    """Announcement-time affordability of `cost` that also leaves a spell's non-mana cost payable: plan_payment, but the
    sources that cannot all be tapped (unusable_for_extra_cost) are held back. Same answer as plan_payment when there is
    no precondition or no self-removing source. Returns True / False."""
    for held_back in unusable_for_extra_cost(state, extra_legal):
        if not held_back:
            if game.plan_payment(state, cost) is not None:
                return True
        elif game.can_pay(game.units_after(state, tapped=held_back), cost):
            return True
    return False


__all__ = [
    '_GATE_NO_PENDING',
    '_begin_cast_payment',
    'cast_extra_legal',
    'taps_away',
    'extra_cost_holds_without',
    'payable_keeping_extra_cost',
    'unusable_for_extra_cost',
    '_hand_count_available',
    'copy_signature',
    'distinct_copies',
]
