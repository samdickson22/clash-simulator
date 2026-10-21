"""Unit tests for the LIVE fidelity harness (no engine, no recordings needed).

    PYTHONPATH=. python -m pytest -q bot/simfid/test_live.py
"""
import itertools
import math
import random
from collections import Counter, defaultdict

from bot.simfid import live_data as LD
from bot.simfid import live_run as LR


def test_hungarian_is_exact_on_rectangular_matrices():
    rng = random.Random(0)
    for _ in range(200):
        n, m = rng.randint(1, 5), rng.randint(1, 5)
        C = [[rng.random() for _ in range(m)] for _ in range(n)]
        got = LR.hungarian(C)
        k = min(n, m)
        best = min(sum(C[i][j] for i, j in zip(rows, cols))
                   for rows in itertools.combinations(range(n), k) for cols in itertools.permutations(range(m), k))
        assert len(got) == k and len({i for i, _ in got}) == k and len({j for _, j in got}) == k
        assert abs(sum(C[i][j] for i, j in got) - best) < 1e-9


def test_assignment_prefers_total_distance_over_greedy():
    # greedy would pair (0,0)-(0,.1) first and leave (0,.3)-(0,-.2) at .5; optimal pairs both at .2
    pairs = LR._assign([(0, 0), (0, .3)], [(0, .1), (0, -.2)])
    assert sorted(round(d, 6) for _, _, d in pairs) == [0.2, 0.2]


def test_level_inference_ties_are_unresolved():
    # 0.5 * every even max HP is an integer: two candidate levels fit equally -> no level
    assert LD.infer_level([.5], {7: [100], 8: [110]})[0] is None
    assert LD.infer_level([.25], {7: [100], 8: [110]})[0] == 7      # 25 vs 27.5: unique fit
    assert LD.infer_level([], {7: [100]})[0] is None


def test_unknown_truth_hp_never_enters_the_hp_denominator():
    acc, cards = Counter(), defaultdict(Counter)
    truth = [LD.Unit('GoblinHut', 'SpearGoblin', 1, 5.0, 20.0, math.nan)]     # projectile-log body, hp unknown
    LR.score_frame(truth, [], {'GoblinHut': ['GoblinHut_Rework']}, acc, cards)
    assert acc['ut'] == 1 and acc['miss'] == 1 and acc['hp_ut'] == 0
    LR.score_frame(truth, [(1, 'GoblinHut', False, 5.0, 20.1, 1.0)], {'GoblinHut': ['GoblinHut_Rework']}, acc, cards)
    assert acc['ut'] == 2 and acc['q'] == 1 and acc['hp_ut'] == 0


def _game(records, plays=(), carriers=()):
    return LD.Game(name='t', deck=list(LD.HOG26), levels={}, records=records, plays=list(plays), end_tick=2000,
                   crowns=None, carriers_at=list(carriers))


def _rec(t, units=()):
    return LD.Record(t, list(units), {}, [], None, None)


def test_quiet_start_rejects_carriers_in_flight_and_recent_plays():
    recs = [_rec(100), _rec(105), _rec(110)]
    assert LR._quiet(_game(recs), 1)
    assert not LR._quiet(_game(recs, carriers=[103]), 1)                     # a public spell carrier in flight
    assert not LR._quiet(_game(recs, plays=[LD.Play(1, 'Zap', 60, 3, 25, 'own')]), 1)   # a play 45 ticks before
    assert not LR._quiet(_game([_rec(100), _rec(105, [LD.Unit('Knight', 'Knight', 1, 3, 20, 1.)])]), 1)
