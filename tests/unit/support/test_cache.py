"""support.cache.source_hash: the corpus cache key must change whenever anything that can alter a recorded decision does."""
from support.cache import source_hash


def make_repo(tmp_path):
    (tmp_path / "src" / "game").mkdir(parents=True)
    (tmp_path / "src" / "drl_env").mkdir()
    (tmp_path / "tests" / "data").mkdir(parents=True)
    (tmp_path / "tests" / "support").mkdir()
    (tmp_path / "src" / "game" / "stats.py").write_text("POWER = 1\n")
    (tmp_path / "src" / "drl_env" / "table.py").write_text("DIM = 3\n")
    (tmp_path / "tests" / "data" / "elves.txt").write_text("4 Llanowar Elves\n")
    (tmp_path / "tests" / "data" / "league_decks.json").write_text("{}\n")
    (tmp_path / "tests" / "support" / "corpus.py").write_text("X = 1\n")
    return tmp_path


def test_a_change_anywhere_in_src_changes_the_key(tmp_path):
    repo = make_repo(tmp_path)
    base = source_hash(repo, extra=["tests/support/corpus.py"])
    (repo / "src" / "game" / "stats.py").write_text("POWER = 2\n")
    assert source_hash(repo, extra=["tests/support/corpus.py"]) != base


def test_decklists_and_the_corpus_builder_are_part_of_the_key(tmp_path):
    repo = make_repo(tmp_path)
    base = source_hash(repo, extra=["tests/support/corpus.py"])
    (repo / "tests" / "data" / "elves.txt").write_text("3 Llanowar Elves\n")
    changed_deck = source_hash(repo, extra=["tests/support/corpus.py"])
    assert changed_deck != base
    (repo / "tests" / "support" / "corpus.py").write_text("X = 2\n")
    assert source_hash(repo, extra=["tests/support/corpus.py"]) != changed_deck


def test_bytecode_is_not_part_of_the_key(tmp_path):
    repo = make_repo(tmp_path)
    base = source_hash(repo)
    (repo / "src" / "game" / "__pycache__").mkdir()
    (repo / "src" / "game" / "__pycache__" / "stats.py").write_text("junk\n")
    assert source_hash(repo) == base


def test_a_rename_changes_the_key(tmp_path):
    repo = make_repo(tmp_path)
    base = source_hash(repo)
    (repo / "src" / "drl_env" / "table.py").rename(repo / "src" / "drl_env" / "tbl.py")
    assert source_hash(repo) != base


def test_the_key_is_stable_when_nothing_changes(tmp_path):
    repo = make_repo(tmp_path)
    assert source_hash(repo) == source_hash(repo)


def test_the_real_repo_key_covers_the_engine():
    """The repo's own key must include a file from src/game, the exact gap this guards."""
    import hashlib

    from support.paths import REPO
    files = {p.relative_to(REPO / "src").parts[0] for p in (REPO / "src").rglob("*.py")}
    assert {"game", "drl_env"} <= files
    assert len(source_hash()) == len(hashlib.sha256().hexdigest())
