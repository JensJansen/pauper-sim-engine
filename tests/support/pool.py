"""The engine suite's deck pool: the fabricated coverage decks in tests/data/decks (every implemented card appears in at
least one), keyed by file stem. `build_pool()` returns the same 4-tuple shape as the policy's `rl.roster.build_pool`
(decklists, vocab, deck_ctxs, fixed_tables) so the suites read alike; there is no vocabulary here, so `vocab` is None and
`deck_ctxs[name] = (None, fixed_table)`."""
import game
from drl_env import action_bridge as AB
from support.paths import DATA_DIR

DECKS_DIR = DATA_DIR / "decks"
TOKEN_DEFS = AB.TOKEN_DEFS


def deck_files():
    return {p.stem: p for p in sorted(DECKS_DIR.glob("*.txt"))}


def build_pool():
    decklists = {name: game.parse_decklist_file(str(path)) for name, path in deck_files().items()}
    fixed_tables = {name: AB.build_fixed_action_table(dl, token_card_defs=TOKEN_DEFS) for name, dl in decklists.items()}
    deck_ctxs = {name: (None, table) for name, table in fixed_tables.items()}
    return decklists, None, deck_ctxs, fixed_tables
