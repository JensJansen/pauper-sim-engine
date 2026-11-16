# pauper-sim-engine

The rules engine of the [pauper_sim](https://github.com/JensJansen/pauper-sim) Magic: the Gathering subset simulator:
the card catalog, the turn/priority/stack loop, and the legal-action table + mask layer a policy plays through.
It has **no ML dependencies** (numpy only) and is consumed by the main repo as a git submodule (`engine/`,
`pip install -e engine`). Importing is unchanged: `import game`, `import drl_env`.

**Rules faithfulness is the highest-priority standing rule here** -- see [CLAUDE.md](CLAUDE.md).

## Layout

```
src/
  game/                    The engine (package). Zero ML deps.
    cards.py                 EffectId / CardType / CardDef -- the card data model.
    state.py                 PlayerState + GameState: zones, turn/stack bookkeeping.
    turn.py                  Phase/Speed enums; priority rounds; mulligan; the turn loop;
                             game_coroutine + run_multiplayer_game.
    mana.py                  Cast-then-pay mana (CR 601.2): plan_payment checks affordability;
                             the agent makes every tap.
    decklist.py              Parse decklist files against CARD_DEFS.
    registry.py              Union of every color catalog -> CARD_DEFS + EFFECT_REGISTRY.
    scenario.py              Hand-built board states for tests (shared with the policy repo's tests).
    catalog/                 Card definitions by color.
    effects/                 Generic effect plumbing: casting, combat, stack + triggers,
                             state_based (SBAs + cleanup), stats, tokens, win_check,
                             madness_and_plot, undercity, shared.
    resolution/              Multi-step decisions made one action at a time: _core (begin/complete
                             state machine) + one handlers_<kind> module per category.
  drl_env/                 Action-table / legal-mask machinery, re-exported flat via __init__.py:
    _actions_common.py       Shared sentinel + hand-count helper.
    _actions_cast.py         Play land / Cast (modal/X/Delve) / Activate / Forestcycle.
    _actions_cast_altzone.py Casting from non-hand zones or alt costs: Flashback, Escape, Plot, Omen, Prototype.
    _actions_combat.py       Attack / Assign Blocker / Done blocking / trample row.
    _actions_resolution.py   Generic pending-resolution dispatch (Pass, by-name choices, permanent targeting, mana spend).
    _actions_mana.py         Mana-ability/extra-cost/filter legal/execute pairs.
    _actions_table.py        build_action_table + legal_action_mask.
    _seat.py                 Per-seat helpers.
    action_bridge.py         The fixed-table / pointer split of the action space: build_fixed_action_table,
                             pointer_legal_mask / execute_pointer_choice / any_pointer_legal / pointer_kind,
                             pointer_identities (what a pointer can address), TOKEN_DEFS.
tests/                     unit/ + component/ + support/ + data/ -- see tests/README.md.
docs/                      SAC_FIZZLE_HYPOTHESES.md (record of the sac-cost crash hypotheses).
```

The only things this repo knows about its consumer are in comments: the policy repo's `rl.model.*` modules index the
action table (row order is load-bearing -- see below) and build the observation the pointer head points into.

**Row order is load-bearing.** A policy's action head has one logit per fixed-table row, so reordering or inserting rows
silently scrambles every saved checkpoint. The pin that guards it (`action_table_snapshot.json`, over the real league
decks) lives in the **parent repo's** tests; a change here that alters any table's row order or labels will fail it and needs
the owner's sign-off.

## The game engine (`src/game/`)

Self-contained, no ML dependency.

- **Turn structure & priority.** Full phase sequence (untap, upkeep, draw,
  main1, declare-attackers, declare-blockers, combat-damage, main2, end)
  with real priority rounds.
- **The stack & triggers.** Spells/abilities go on the stack and resolve;
  triggers queue and get promoted to the stack.
- **Combat.** Attackers/blockers, summoning sickness, per-permanent
  identity, gang-blocking, menace, a first-strike sub-step, and removal
  from combat (506.4); a blocked creature stays blocked even if every
  blocker dies (509.1h).
- **Mana — cast then pay (CR 601.2).** See below.
- **Card mechanics.** Madness, plot, flashback, auras/bestow, scry/surveil,
  fetch/search, initiative/Undercity, mulligans, token generation (Blood,
  Robot, Warrior, Eldrazi Spawn, Food, Clue, Treasure, and more),
  affinity/delve/escape cost reduction, state-based actions, decking out,
  life-total win checks.
- **Game end.** A life total at 0 or less, or decking out, ends the game:
  `state.turn_won` is set and `game.turn` asks no one for anything further and
  resolves nothing further (it finishes the effect that decided the game, then
  stops). One effect taking both players to 0 is a draw (`state.winner` None,
  `state.is_draw` True).

> **AUTHORIZED SIMPLIFICATION** (owner-approved 2026-11-16). The game ends as
> soon as the effect that took a life total to 0 has finished resolving, not
> at the next state-based-action check (704.5a), so a life total cannot
> recover above 0 first; the first player to reach 0 loses unless the same
> effect also takes the other player to 0 (a draw, 104.4a).

### Mana: cast then pay

Real Magic announces a spell, settles modes/X/targets, determines total cost
(601.2e), then activates mana abilities (601.2f) and pays (601.2g). Every
affordability gate is `game.plan_payment(state, cost) is not None` — could
the floating pool plus whatever's still tappable cover this? The agent makes
every tap; the solver only decides whether a cost is payable.

**Exact solver**, via the deficiency form of Hall's theorem: payable iff
there are at least as many mana units as pips, and for every subset of
colours demanded, at least that many units can produce one of them. At most
six colours can be demanded, so the subset sweep is <=63 iterations.

**Stranding invariant.** A payment can't be abandoned, so any action taken
mid-payment that reduces available mana is gated on the payment surviving
it. A dual-colour source counts as one unit until tapped, so tapping it for
the wrong colour can strand a payment; filters and cost-paid mana sources
(e.g. Saruli Caretaker) are handled the same way. `begin_pay_cost` asserts
the invariant itself.

Mana abilities are illegal for the whole of an in-flight cast before 601.2f
(no player receives priority during 601.2).

> **AUTHORIZED SIMPLIFICATION** (owner-approved 2026-08-17). Speculative
> floating — a mana ability activated with no payment open — is restricted
> to the active player's own main phase, instead of any priority window as
> in real Magic. Low cost in practice: holding mana up just means leaving
> lands untapped, and paying for an instant on the opponent's turn goes
> through the payment window anyway.

The engine tolerates a no-opponent (1-player) configuration for card-level
unit tests, but the active surface, and everything the DRL system drives,
is 2-player (the policy repo's DRL pipeline is 2-player only).

---

---

## Setup

```
pip install -r requirements.txt     # numpy, pytest, ruff
pip install -e .                    # makes `import game, drl_env` work from anywhere (a plain `pytest` from the root works without it)
git config core.hooksPath .githooks # pre-commit: ruff; pre-push: unit tier
```

## Tests and lint

See [tests/README.md](tests/README.md). `pytest tests/unit` is seconds; `pytest tests/component` is the action-space suite
(corpus of seeded random-legal games over the coverage decks, an independent rules oracle, exhaustive searches).
`ruff check src tests` must report "All checks passed!" (bug-finding and dead-code rules only; config in `pyproject.toml`).
