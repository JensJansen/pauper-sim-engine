"""Planted bugs for the STATE-INTEGRITY component: each re-introduces one of the defects this suite found and the engine
then fixed (F-04, F-05, F-06), so a survivor means the invariants no longer keep that fix in place.

Run:  python tests/support/mutation_sweep.py state_integrity          (all)  |  ... state_integrity 2 4  |  ... --baseline

Each entry: (file under src/, exact old text -- must occur exactly once --, replacement, what bug it models)."""

COMPONENT = "state_integrity"
TIMEOUT = 900
SI = "tests/component/state_integrity"
TEST_PATHS = [f"{SI}/test_i2_checker_and_findings.py", "tests/unit/game/catalog/test_colorless_cards.py", f"{SI}/test_i1_invariants.py"]
ENV = {}

C = "drl_env/_actions_cast.py"
SB = "game/effects/state_based.py"

MUTATIONS = [
    # --- F-04: payments that are not casts must not leave casting_depth counting one ---
    (C, "game.begin_pay_cost(state, card_def.extra[cost_key], on_complete=lambda s: resolve(s, card_def), counts_as_cast=False)",
     "game.begin_pay_cost(state, card_def.extra[cost_key], on_complete=lambda s: resolve(s, card_def))",
     "F-04 back: cycling / Forestcycling counts as a cast and never uncounts"),
    (C, "game.begin_pay_cost(state, p.card_def.extra[cost_key], on_complete=lambda s: resolve(s, p), counts_as_cast=False)",
     "game.begin_pay_cost(state, p.card_def.extra[cost_key], on_complete=lambda s: resolve(s, p))",
     "F-04 back: an activated ability (Map's explore) counts as a cast and never uncounts"),
    ("drl_env/_actions_cast_altzone.py", "on_complete=lambda s: resolve(s, card_def), counts_as_cast=False)",
     "on_complete=lambda s: resolve(s, card_def))", "F-04 back: Plot counts as a cast and never uncounts"),
    # --- F-05: 704.5m ---
    (SB, "    orphan_unattached_auras(state)  # 704.5m: also catches a non-creature that left some other way",
     "    pass", "F-05 back: an Aura whose non-creature permanent left stays on the battlefield"),
    (SB, 'and id(p.flags["enchanting"]) not in on_bf]', 'and False]',
     "F-05 back: the orphan sweep never finds a dangling Aura"),
    # --- F-06 ---
    ("game/catalog/colorless_cards.py",
     "    if card_def in state.hand:  # already left hand at cast; only a direct call (self-check) still has it there\n        state.hand.remove(card_def)\n    exiled = []",
     "    discard_from_hand_to_graveyard(state, card_def)\n    exiled = []",
     "F-06 back: the resolving Maelstrom Colossus is discarded to the graveyard and then enters the battlefield"),
]
