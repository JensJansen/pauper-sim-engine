# Component: determinism (a game is a function of decks, seed and actions)

**Contract.** The same decks + seed + chosen actions always produce the same game, state for state. The action-space suite
depends on it (`support/fork.py` replays a game from its seed when a state cannot be deep-copied safely) and so does any
reproducing of a training game from its seed. Every test compares a digest of the full deep state fingerprint at EVERY
decision (`support/trace.py`), so a divergence is pinned to the first decision where it appears.

| File | What it establishes |
|---|---|
| `test_d1_replay.py` | D1 the same seed twice; D2 replaying the recorded actions (the fork-fallback path); D3 another game in between leaves no trace (module-level caches); D4 turning the event log on changes nothing (except the `_logged_pt` viewer bookkeeping flag, which only refreshes while logging) |
| `test_d5_process.py` | D5 the same four games in separate processes with different `PYTHONHASHSEED`s are identical (no string-hash-ordered iteration reaches a decision) |

**Cost.** ~1.5 min. Knob: `DETERMINISM_GAMES` (default 24 sampled deck pairs).
