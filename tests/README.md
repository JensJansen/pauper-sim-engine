# Tests

Two tiers, each a folder. Unit tests mirror `src/`; components are named for the subsystem they stress.

| Tier | What it is | Where |
|---|---|---|
| **Unit** | One card, function or rule, with fabricated inputs. Deterministic. | `tests/unit/` (`unit/game/catalog/…`, `unit/game/effects/…`, `unit/drl_env/…`) |
| **Component** | A subsystem tested against its *contract* over real games: independent oracles, invariance checks, coverage gates, exhaustive searches, planted bugs. | `tests/component/<name>/` (today: `action_space`) |

The tier marker (`unit` / `component`) is applied automatically from the folder, so `pytest -m unit` and
`pytest tests/unit` are the same.

```
pip install -r requirements.txt && pip install -e .
pytest tests/unit                          # seconds -- also the pre-push gate
pytest tests/component/action_space        # the action-space component
pytest tests                               # everything
python tests/support/mutation_sweep.py action_space   # plant deliberate bugs, report any the suite misses
```

## Policies
- **Push gate:** `.githooks/pre-push` runs `tests/unit`; a failure blocks the push. Lint gates commits. Enable once per
  clone with `git config core.hooksPath .githooks`.
- **Golden pins need the owner's sign-off.** A pin failing means either an accident or a deliberate change that invalidates
  something downstream. Regenerating one is a deliberate, reviewed act, never a way to make a red test green. (The
  action-table row-order pin guards trained checkpoints, so it lives in the *parent* repo, next to the checkpoints:
  `tests/component/action_space/test_action_table_order.py` there.)
- **Planted-bug lists are maintained together.** Each component keeps `mutations.py`: deliberate bugs, planted one at a time
  in a scratch copy of `src/` (the real tree is never touched). A surviving mutation is a hole in that component's tests.
  When behavior changes, add the mutation that guards it.

## No policy network here
Nothing in this repo imports the policy stack. Tests that need to play real games use the engine-native agents in
`support/agents.py`:
- `FirstLegalAgent` -- always the lowest-index legal action; fully deterministic, for tests that need consistency.
  It can fail to make progress (a repeatable legal action can be first forever), so use a turn horizon.
- `SeededRandomAgent(seed)` -- uniform over legal actions from its own `random.Random`, so a seed replays exactly. The
  action-space corpus uses it.

## Test data (`tests/data/`)
- `decks/coverage_*.txt` -- **fabricated** decks that together contain every implemented card (`tests/unit/test_decks.py`
  fails when a new card is not in one). The action-space suite plays these.
- `*.txt`, `league_decks.json` -- a **frozen copy** of the main repo's league decklists, for regression tests that were
  written against specific real decks (Tron's filters, Spy, DFC faces). A snapshot: it does not track the main repo.

## Shared infrastructure: `tests/support/`
`paths`, `fixtures` (cwd = `src/`), `pool` (the deck pool + fixed tables), `agents` (the decision builder and agents above),
`action_corpus` (seeded random-legal self-play with an on-decision hook, compared against `action_oracle`, an independent
rules oracle), `fingerprint` (deep identity-canonical state fingerprint), `fork` (throw-away forks of live positions),
`search` (exhaustive search over mask-legal move sequences), `cache` (corpus cache keys: a hash of all of `src/`, the decks
and the corpus/oracle code), `mutation_sweep`. Board builders for hand-made positions are `game.scenario`.
