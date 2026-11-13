"""Hand-built two-player board states for tests: a declarative spec -> GameState, plus a mirror (swap the two seats).
Shared by this repo's suites and the policy repo's encoder tests (which add the tokenizer/encoder half themselves)."""
import copy

import game
from game.state import CardInstance, GameState, Permanent, PlayerState

NAMES = ("Guttersnipe", "Kitchen Imp", "Mountain", "Island", "Lightning Bolt", "Counterspell", "Rancor",
         "Ancestral Mask", "Faithless Looting", "Balustrade Spy", "Galvanic Blast")


def seat(bf=(), gy=(), ex=(), hand=()):
    """One seat. bf items: a name, or (name, {flag: value}) with flags tapped / sick / counters / damage / aura_on
    (index into the SAME seat's bf, or (other_seat_flag, index) is not needed here), slot."""
    return {"bf": list(bf), "gy": list(gy), "ex": list(ex), "hand": list(hand)}


def build(s0, s1, stack=(), attackers=None, blocked=None):
    """stack: [(name, controller, target)] with target None, ("bf"|"gy", seat_idx, index) or ("player", seat_idx).
    attackers: {seat: [bf index]}.  blocked: {seat_of_attackers: {attacker_index: [(blocker_seat, blocker_index)]}}."""
    players = [PlayerState(on_the_play=True), PlayerState(on_the_play=False)]
    perms = [[], []]
    for i, spec in enumerate((s0, s1)):
        pl = players[i]
        for item in spec["bf"]:
            name, flags = (item, {}) if isinstance(item, str) else item
            p = Permanent(game.CARD_DEFS[name], tapped=flags.get("tapped", False))
            p.summoning_sick = flags.get("sick", False)
            p.counters = dict(flags.get("counters", {}))
            p.damage_marked = flags.get("damage", 0)
            p.slot = flags.get("slot", 1 + sum(1 for q in perms[i] if q.card_def.name == name))
            perms[i].append(p)
        pl.battlefield = perms[i]
        pl.graveyard = [CardInstance(game.CARD_DEFS[n]) for n in spec["gy"]]
        pl.exile = [(game.CARD_DEFS[n], None) for n in spec["ex"]]
        pl.hand = [game.CARD_DEFS[n] for n in spec["hand"]]
    for i, spec in enumerate((s0, s1)):  # auras attach after every permanent exists
        for j, item in enumerate(spec["bf"]):
            if not isinstance(item, str) and "aura_on" in item[1]:
                tgt_seat, tgt_idx = item[1]["aura_on"]
                perms[i][j].flags["enchanting"] = perms[tgt_seat][tgt_idx]
    state = GameState(on_the_play=True, players=players)
    objs = {"bf": perms, "gy": [players[0].graveyard, players[1].graveyard]}
    state.stack = []
    for name, controller, target in stack:
        targets = ()
        if target is not None and target[0] == "player":
            targets = (("player", target[1]),)
        elif target is not None:
            zone, s, idx = target
            targets = (("creature" if zone == "bf" else "graveyard_card", objs[zone][s][idx]),)
        state.stack.append({"card_def": game.CARD_DEFS[name], "resolve": None, "controller": controller, "targets": targets})
    for i, idxs in (attackers or {}).items():
        players[i].attackers = [perms[i][k] for k in idxs]
    for i, mapping in (blocked or {}).items():
        players[i].blocked_by = {perms[i][a]: [perms[bs][bi] for bs, bi in blockers] for a, blockers in mapping.items()}
    return state


def mirror(args):
    """The same position with the two seats swapped (kwargs for build())."""
    s0, s1 = args["s0"], args["s1"]
    def flip(i):
        return 1 - i
    out = {"s0": copy.deepcopy(s1), "s1": copy.deepcopy(s0)}
    for sp in out.values():
        for _k, item in enumerate(sp["bf"]):
            if not isinstance(item, str) and "aura_on" in item[1]:
                item[1]["aura_on"] = (flip(item[1]["aura_on"][0]), item[1]["aura_on"][1])
    out["stack"] = [(n, flip(c), None if t is None else (t[0], flip(t[1])) + tuple(t[2:])) for n, c, t in args.get("stack", ())]
    out["attackers"] = {flip(i): v for i, v in (args.get("attackers") or {}).items()}
    out["blocked"] = {flip(i): {a: [(flip(bs), bi) for bs, bi in bl] for a, bl in m.items()}
                      for i, m in (args.get("blocked") or {}).items()}
    return out


# A busy, asymmetric position used by several tests: counters, damage, an aura, graveyards, exile, a two-spell stack, and a
# blocked attacker.
BUSY = {
    "s0": seat(bf=[("Guttersnipe", {"counters": {"+1/+1": 1}}), ("Mountain", {"tapped": True}), ("Rancor", {"aura_on": (0, 0)})],
               gy=["Faithless Looting"], ex=["Lightning Bolt"], hand=["Counterspell"]),
    "s1": seat(bf=[("Kitchen Imp", {"damage": 1}), "Island"], gy=["Counterspell", "Lightning Bolt"]),
    "stack": [("Lightning Bolt", 1, ("bf", 0, 0)), ("Counterspell", 0, None)],
    "attackers": {1: [0]}, "blocked": {1: {0: [(0, 0)]}},
}
