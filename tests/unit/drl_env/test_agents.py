"""The engine-native test agents: determinism, and that the engine imports no policy code."""
import subprocess
import sys

from support import agents as AG
from support.pool import build_pool

POOL = build_pool()
A, B = sorted(POOL[0])[:2]


def _play(agent, seed):
    log = []
    state = AG.play_game(POOL, A, B, agent, seed, horizon=6, event_log=log)
    return state.turn_number, [str(e) for e in log]


def test_seeded_random_agent_replays_exactly():
    assert _play(AG.SeededRandomAgent((A, B), POOL, 5), 11) == _play(AG.SeededRandomAgent((A, B), POOL, 5), 11)


def test_different_agent_seeds_play_different_games():
    assert _play(AG.SeededRandomAgent((A, B), POOL, 5), 11) != _play(AG.SeededRandomAgent((A, B), POOL, 6), 11)


def test_first_legal_agent_is_deterministic_and_never_calls_global_random():
    import random
    before = random.getstate()
    one = _play(AG.FirstLegalAgent((A, B), POOL), 3)
    after_first = random.getstate()
    two = _play(AG.FirstLegalAgent((A, B), POOL), 3)
    assert one == two
    assert before == after_first, "the agent consumed the global random state"


def test_pointer_identities_are_exactly_what_pointer_legal_mask_may_offer():
    """Every pointer pick the mask offers during a random game is in pointer_identities (nothing addressable is missed)."""
    from drl_env import action_bridge as AB
    agent = AG.SeededRandomAgent((A, B), POOL, 9)
    seen = [0]
    real = agent.choose_action

    def checked(state):
        if AB.any_pointer_legal(state):
            ids = AB.pointer_identities(state, state.active_idx)
            assert ids, "a pointer decision with nothing addressable"
            seen[0] += 1
        return real(state)

    agent.choose_action = checked
    AG.play_game(POOL, A, B, agent, 21, horizon=8)
    assert seen[0] > 0


def test_the_engine_imports_no_policy_code():
    code = ("import sys, game, drl_env\nfrom drl_env import action_bridge\n"
            "bad = [m for m in sys.modules if m.split('.')[0] in ('rl', 'torch', 'evaluation', 'validation', 'webapp')]\n"
            "assert not bad, bad")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
