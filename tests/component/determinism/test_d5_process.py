"""D5: the same game in separate processes with different hash seeds.

Python randomizes str hashing per process (PYTHONHASHSEED). Any place the engine iterates a set / dict keyed by strings and
lets the order reach a decision (which card is "first", which source is tried) makes a game differ between processes while
passing every in-process test. Each child plays the same few games and prints one digest over all their states.
"""
import os
import subprocess
import sys

import pytest

from support.paths import REPO, SRC

CHILD = r"""
import hashlib, os, sys
sys.path[:0] = [os.environ["ENGINE_SRC"], os.environ["ENGINE_TESTS"]]
os.chdir(os.environ["ENGINE_SRC"])
from support import trace as T
h = hashlib.sha256()
for a, b, gi in [("coverage_1", "coverage_2", 0), ("coverage_3", "coverage_4", 1), ("coverage_2", "coverage_2", 2),
                 ("coverage_4", "coverage_1", 3)]:
    t = T.run_game(a, b, gi)
    h.update(repr((t.chosen, t.digests, t.error)).encode())
print(h.hexdigest())
"""


def _run(hash_seed):
    env = {**os.environ, "PYTHONHASHSEED": str(hash_seed), "ENGINE_SRC": str(SRC), "ENGINE_TESTS": str(REPO / "tests")}
    out = subprocess.run([sys.executable, "-I", "-c", CHILD], env=env, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout.strip()


def test_d5_games_do_not_depend_on_the_hash_seed():
    digests = {seed: _run(seed) for seed in (0, 1, 12345)}
    assert len(set(digests.values())) == 1, f"the same games differ between processes: {digests}"
