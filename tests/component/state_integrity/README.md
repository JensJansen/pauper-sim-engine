# Component: state integrity (whole-game invariants)

**Contract.** Whatever the cards did, at every decision of every real game the position is *sane*: cards are in one place
and never duplicated, pools and counters are non-negative, Auras enchant something that is still there, combat refers to
creatures that exist, state-based actions are done whenever a player could act, and the engine's own `casting_depth`
bookkeeping is not left dangling. These are facts the rules guarantee, checked by code that shares nothing with the engine's
own bookkeeping (`support/invariants.py` reads raw state only).

| File | What it establishes |
|---|---|
| `support/invariants.py` | `check(state, baseline)` -> `[(invariant_id, message)]`; ids in `IDS` |
| `test_i1_invariants.py` | one test per invariant over ~129k decisions (every ordered deck pair, random-legal self-play); a **coverage gate** that the corpus actually contains Auras, attackers, blocks, tokens, same-named permanents, stack entries, pools, counters, damage, 25+ pending kinds |
| `test_i2_checker_and_findings.py` | the checker itself: a hand-built position that breaks each invariant must fire it (a checker that never fires proves nothing);  |

**Findings (all fixed 2026-11-13; the invariants keep them fixed).**
- **F-04** `casting_depth` leaked after Forestcycle / Cycle, a Map's explore and Plot: they opened their payment as a cast but never reached
  `push_to_stack`. Cycling, activated abilities (explore) and Plot are not casts, so they now pay with `counts_as_cast=False`.
- **F-05** an Aura outlived a non-creature permanent it enchanted (Crop Rotation sacrificing an enchanted land). 704.5m is now a state-based
  action: `state_based.orphan_unattached_auras`, run by `check_state_based_actions` and on creature death.
- **F-06** Maelstrom Colossus was in the graveyard AND on the battlefield after resolving; its cascade no longer discards the resolving spell.

**Not checked, on purpose.** A card disappearing: exile is only tracked for castable cards (plot / madness), so a card exiled by
Relic of Progenitus, Bojuka Bog, Masked Vandal or flashback legitimately leaves every tracked zone and cannot be told from a loss.
Observed, not a finding: the engine models a spell with an eager alt cost (Crop Rotation, Fireblast) as already in the graveyard while it is
on the stack.

**Cost.** ~1 min (corpus, not cached). Knob: `INTEGRITY_GAMES` (games per ordered pair, default 3).
