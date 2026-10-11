"""PREREG-K4S smoke-health (outcome-blind) value/nullability tests (Sol core r3 finding 17)."""
import copy, hashlib, json
from health import health
from schedule import block

GOOD = dict(hit=False, fallback=False, completed=8, candidates=9, unpruned_candidate_count=9, own_elixir=5., fallback_action=2304, threads=4,
            coarse_horizon=160, default_source='SD1', wall_overrun=False, overrun_seconds=0., delayed_ticks=0, decision_tick=100, action=7,
            wall_seconds=.1, cpu_seconds=.1, coarse_complete=True, coarse_scored=3, plays=3, frozen_action=7, student_default=False,
            sd1_default_action=2304, sd1_p_play=.2, coarse_order_sha256='x', chosen_action=7, fallback_used=False, selected_wait_ticks=0,
            poll_seconds=.01, scale_sleep_seconds=0., prep_seconds=.03, scored=True, positive_overrun_ms=0., charged_extra_ticks=0)


def tree(tmp_path, mutate=None):
    d = block('smoke', 0); d['order'] = ['K4S-200']
    root = tmp_path/'r'; g = root/d['id']/'games'; g.mkdir(parents=True)
    stats = [dict(GOOD)]
    if mutate: stats = mutate(stats)
    game = dict(cohort='K4S-200', metadata=dict(terminal=True, cell=d['cell'], seat=d['seat'], seed=d['seed'], speed_cell=1.0, budget_ms=200,
                inference_scale=1.0, scale_mode='poll', kernel='K4-anytime-sdefault', default_source='SD1', block_id=d['id'], rotation=d['rotation']),
                search_ab=dict(nice=10, scheduler=0, worker_affinity=[0, 1, 2, 3, 4], gc_maintenance=[], policy_cache_counts=dict(forward=1, fallback=1),
                               deadline_stats=stats, latency_seconds=[s['wall_seconds'] for s in stats]))
    raw = json.dumps(game).encode(); name = f"{d['id']}-d27-K4S-200.json"; (g/name).write_bytes(raw)
    (root/d['id']/'complete.json').write_text(json.dumps(dict(descriptor=d, host='127x01', slot_cores=[0, 1, 2, 3, 4], games={name: hashlib.sha256(raw).hexdigest()})))
    return root


def errors(tmp_path, mutate=None):
    return health(tree(tmp_path, mutate), validate=True)['errors']


def test_valid_decision_passes(tmp_path):
    assert errors(tmp_path) == []


def test_empty_decisions_fail(tmp_path):
    assert any('no decisions' in e for e in errors(tmp_path, lambda s: []))


def test_sd1_and_alias_nullability_fail(tmp_path):
    for k, v in (('sd1_default_action', None), ('coarse_order_sha256', None), ('chosen_action', 8), ('plays', None), ('fallback_used', True)):
        def m(s, k=k, v=v): s = copy.deepcopy(s); s[0][k] = v; return s
        assert any('SD1/scan/alias' in e for e in errors(tmp_path/k, m)), k
