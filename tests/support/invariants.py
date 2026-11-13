"""Whole-state invariants: facts that must hold at EVERY decision of EVERY real game, whatever the cards did.

`check(state, baseline)` returns a list of (invariant_id, message); empty = the position is sane. It reads raw engine
state only (no drl_env, no mask), and shares no code with the engine's own bookkeeping, so it can disagree with it.

`baseline(state)` is taken once at the first decision and carries what conservation needs: each seat's starting
card multiset (name -> count). Tokens (`name not in CARD_DEFS`) are created and destroyed freely and are not counted.

Card-conservation rule: for every seat and every real card name, the copies found across that seat's tracked zones
(library, hand, battlefield, graveyard, exile, impulse) may never EXCEED the starting count -- a duplicated card is always a
bug. The count may fall: exile is only tracked for castable cards (plot / madness), so a card exiled by a graveyard-hate
effect, Masked Vandal or flashback simply leaves every tracked zone. That is not checked (it cannot be told from a lost card).
"""
from collections import Counter

from game.effects import stats
from game.effects.state_based import departing_card_def, is_token
IDS = ("idx", "stack", "pool", "counter", "zones", "slots", "perm", "combat", "conservation", "casting_depth", "aura", "sba")


def baseline(state):
    """Each seat's starting real-card multiset, read from every zone at the first decision (before any card has moved)."""
    return [_zone_counts(state, seat) for seat in range(len(state.players))]


def _card_name(x):
    cd = getattr(x, "card_def", x)
    return cd.name


def _zone_counts(state, seat):
    pl = state.players[seat]
    c = Counter()
    for card in pl.library:
        c[_card_name(card)] += 1
    for card in pl.hand:
        c[_card_name(card)] += 1
    for p in pl.battlefield:
        c[departing_card_def(p).name] += 1
    for card in pl.graveyard:
        c[_card_name(card)] += 1
    for cd, _ in pl.exile:
        c[cd.name] += 1
    for cd, _ in pl.impulse:
        c[cd.name] += 1
    return {n: k for n, k in c.items() if not is_token(n)}


def check(state, base):
    out = []
    add = lambda inv, msg: out.append((inv, msg))  # noqa: E731
    n = len(state.players)

    # ---- indices and counters -------------------------------------------------------------------------------------
    if not 0 <= state.active_idx < n:
        add("idx", f"active_idx {state.active_idx}")
    if not 0 <= state.turn_player_idx < n:
        add("idx", f"turn_player_idx {state.turn_player_idx}")
    if state.casting_depth < 0:
        add("casting_depth", f"negative: {state.casting_depth}")
    if state.casting_depth > 0 and state.pending_resolution is None and state.mana_subdecision is None:
        add("casting_depth", f"{state.casting_depth} cast(s) in flight but no decision is open to finish them")
    for e in state.stack:
        if not 0 <= e["controller"] < n:
            add("stack", f"entry {e['card_def'].name} controller {e['controller']}")

    # ---- per-player facts -----------------------------------------------------------------------------------------
    seen_objs = {}
    for seat, pl in enumerate(state.players):
        who = f"seat {seat}"
        for sym, k in pl.mana_pool.items():
            if sym == "generic":
                add("pool", f"{who}: 'generic' key in the pool")
            if k < 0:
                add("pool", f"{who}: pool[{sym}] = {k}")
        for sym, k in pl.mana_pool_single_pip.items():
            if k < 0 or k > pl.mana_pool.get(sym, 0):
                add("pool", f"{who}: single_pip[{sym}]={k} vs pool={pl.mana_pool.get(sym, 0)}")
        if pl.lands_played_this_turn < 0:
            add("counter", f"{who}: lands_played {pl.lands_played_this_turn}")

        # tokens and real cards alike must be distinct objects, in exactly one zone list
        for zone, items in (("battlefield", pl.battlefield), ("graveyard", pl.graveyard)):
            for it in items:
                key = id(it)
                if key in seen_objs:
                    add("zones", f"{who}: {it!r} is in {zone} and also {seen_objs[key]}")
                seen_objs[key] = f"{who} {zone}"
        iids = [it.iid for it in pl.battlefield + pl.graveyard if it.iid is not None]
        if len(iids) != len(set(iids)):
            add("zones", f"{who}: duplicate iid among battlefield/graveyard")

        slots = Counter((p.card_def.name, p.slot) for p in pl.battlefield)
        for (nm, sl), k in slots.items():
            if k > 1:
                add("slots", f"{who}: two {nm} share slot {sl}")

        bf_ids = {id(p) for p in pl.battlefield}
        for p in pl.battlefield:
            if p.damage_marked < 0:
                add("perm", f"{who}: {p!r} damage_marked {p.damage_marked}")
            for kind, k in p.counters.items():
                if k < 0:
                    add("perm", f"{who}: {p!r} counter {kind} = {k}")
        for a in pl.attackers:
            if id(a) not in bf_ids:
                add("combat", f"{who}: attacker {a!r} is not on the battlefield")
        for attacker, blockers in pl.blocked_by.items():
            for b in blockers:
                if not any(id(b) == id(q) for o in state.players for q in o.battlefield):
                    add("combat", f"{who}: blocker {b!r} is not on any battlefield")

        # ---- conservation -----------------------------------------------------------------------------------------
        zones = _zone_counts(state, seat)
        for nm, k in zones.items():
            if k > base[seat].get(nm, 0):
                add("conservation", f"{who}: {k} x {nm} but the deck started with {base[seat].get(nm, 0)} (duplicated)")

    # ---- auras point at something that is still there ------------------------------------------------------------
    at_priority = state.pending_resolution is None and state.casting_depth == 0 and state.mana_subdecision is None
    on_bf = {id(p) for pl in state.players for p in pl.battlefield}
    for pl in state.players:
        for p in pl.battlefield:
            tgt = p.flags.get("enchanting")
            if at_priority and tgt is not None and id(tgt) not in on_bf:  # 704.5m
                add("aura", f"{p!r} enchants {tgt!r}, which left the battlefield")

    # ---- state-based actions are done whenever a player could act -------------------------------------------------
    if at_priority and state.turn_won is None:
        by_target = stats.enchanting_by_target(state)
        for pl in state.players:
            for p in pl.battlefield:
                if p.card_type.name == "CREATURE":
                    tough = stats.permanent_toughness(state, p, enchanting_auras=by_target.get(id(p), ()))
                    if p.damage_marked >= tough or p.flags.get("deathtouched"):
                        add("sba", f"{p!r} should have died (damage {p.damage_marked}, toughness {tough}) "
                                   f"phase={state.phase}")
        for seat, pl in enumerate(state.players):
            if pl.life_total <= 0:
                add("sba", f"seat {seat} at {pl.life_total} life and the game goes on")
    return out
