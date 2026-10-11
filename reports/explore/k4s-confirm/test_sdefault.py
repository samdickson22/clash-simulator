"""PREREG-K4S injected-clock tests for the SD1 cutoff default (full rule).

Ported from reports/explore/x4s2/test_sdefault.py (sha256 e856f525...): the full-rule tests are
unchanged; lite-only tests are dropped and their coarse_complete statistics checks kept under the full rule.
"""
from types import SimpleNamespace
from anchor_x import anytime, STYLES
from sdefault import apply_default

STUDENT = 3  # a legal play the student would make


class Clock:
    now = 0.
    def __call__(self): return self.now


def core():
    return SimpleNamespace(config=SimpleNamespace(horizon=160), selected_wait_ticks=None,
        info=SimpleNamespace(packet=SimpleNamespace(observation=SimpleNamespace(global_features=[0]*5+[.5]))))


def run(candidates, deadline, default, cost=.01, values=None, threads=1 ):
    c, clock, calls = core(), Clock(), []
    def evaluate(a, s, h, r, root):
        calls.append((a, s, h)); clock.now += cost
        return (values or {}).get((a, s), a/10000)
    frozen = anytime(c, None, 0, candidates, deadline, default, threads=threads,
                     clock=clock if threads == 1 else (lambda: 0.) if deadline is None else clock,
                     evaluate=evaluate)
    return c, frozen, apply_default(c, frozen, default, candidates), calls


def test_zero_budget_returns_student_play():
    c, frozen, action, calls = run([1, 3, 2304, 2400, 2401], 0., STUDENT)
    assert calls == [] and frozen == STUDENT and action == STUDENT
    assert c.deadline_stats['student_default'] and c.selected_wait_ticks == 0


def test_cutoff_after_waits_before_scan_returns_student_not_wait():
    # WAIT completes (3 rollouts), cutoff during timed waits/scan.
    c, frozen, action, calls = run([1, 3, 2304, 2400, 2401, 2402], .045, STUDENT)
    assert frozen == 2304 and action == STUDENT
    assert c.deadline_stats['student_default'] and c.deadline_stats['frozen_action'] == 2304
    assert c.selected_wait_ticks == 0


def test_cutoff_mid_scan_returns_student():
    c, frozen, action, calls = run([1, 2, 3, 2304, 2400], .045, STUDENT)
    assert frozen in (2304, 2400) and action == STUDENT


def test_completed_play_keeps_frozen_rule():
    values = {(a, s): 10. for a in (1, 2) for s in STYLES}
    c, frozen, action, calls = run([1, 2, 2304, 2400], .075, STUDENT, values=values)
    assert frozen == 1 and action == 1 and not c.deadline_stats['student_default']


def test_student_wait_keeps_frozen_wait_choice():
    values = {(2401, s): 5. for s in STYLES}
    c, frozen, action, calls = run([1, 2, 2304, 2400, 2401], .065, 2304, values=values)
    assert frozen == 2401 and action == 2401 and not c.deadline_stats['student_default']


def test_no_deadline_identical_to_anchor():
    for threads in (1, 4):
        c, frozen, action, calls = run(list(range(12))+[2304, 2400, 2401, 2402], None, STUDENT, threads=threads)
        assert action == frozen and not c.deadline_stats['hit'] and not c.deadline_stats['student_default']


def test_no_play_candidates_keeps_frozen():
    c, frozen, action, calls = run([2304, 2400], 0., STUDENT)
    assert frozen == STUDENT  # nothing completed: frozen fallback is the student action anyway
    assert not c.deadline_stats['student_default']


def test_four_threads_cutoff_returns_student():
    # Real wall clock with a slow evaluator: WAIT alone takes ~3x5 ms > 1 ms budget.
    import time
    c = core()
    def evaluate(a, s, h, r, root):
        time.sleep(.005); return 0.
    deadline = time.monotonic()+.001
    frozen = anytime(c, None, 0, [1, 3, 2304, 2400], deadline, STUDENT, threads=4, evaluate=evaluate)
    assert apply_default(c, frozen, STUDENT, [1, 3, 2304, 2400]) == STUDENT


def test_complete_coarse_scan_without_refined_play_uses_sd1_play():
    # WAIT .03, coarse plays .05; refine of play 1 times out at .07 > .065: no refined play.
    c, frozen, action, calls = run([1, 3, 2304, 2400], .065, STUDENT)
    st = c.deadline_stats
    assert st['hit'] and st['coarse_complete'] and st['coarse_scored'] == 2 and st['plays'] == 2
    assert frozen in (2304, 2400) and action == STUDENT
    assert st['student_default'] and st['default_rule'] == 'full' and st['frozen_action'] == frozen


def test_incomplete_coarse_scan_stats():
    c, frozen, action, calls = run([1, 3, 2304, 2400], .045, STUDENT)
    st = c.deadline_stats
    assert st['hit'] and not st['coarse_complete'] and st['coarse_scored'] == 1
    assert action == STUDENT and st['student_default'] and c.selected_wait_ticks == 0


def test_no_deadline_coarse_complete():
    for threads in (1, 4):
        c, frozen, action, calls = run(list(range(12))+[2304, 2400, 2401, 2402], None, STUDENT, threads=threads)
        assert action == frozen and c.deadline_stats['coarse_complete'] and not c.deadline_stats['student_default']


def test_coarse_complete_counts_late_collected_scores_four_threads():
    # Workers see time 0; the collector (main thread) sees the cutoff only after every coarse rollout has
    # returned, so all coarse scores are kept although the phase reports a hit.
    import threading, time as _t
    main = threading.main_thread()
    done = {'coarse': 0}
    c = core()
    plays = [1, 2, 3]
    def evaluate(a, s, h, r, root):
        if a < 2304 and s == STYLES[0]:
            done['coarse'] += 1
        return a/10000
    def clock():
        if threading.current_thread() is not main:
            return 0.
        if done['coarse'] >= len(plays):
            _t.sleep(.05)  # let the finished futures settle before the collector notices the cutoff
            return 10.
        return 0.
    frozen = anytime(c, None, 0, plays+[2304, 2400], 1., STUDENT, threads=4, clock=clock, evaluate=evaluate)
    st = c.deadline_stats
    assert st['hit'] and st['coarse_scored'] == 3 and st['coarse_complete']
    assert apply_default(c, frozen, STUDENT, plays+[2304, 2400]) == STUDENT


def test_empty_play_set_is_coarse_complete_and_keeps_frozen():
    c, frozen, action, calls = run([2304, 2400, 2401], .015, STUDENT)
    assert c.deadline_stats['coarse_complete'] and action == frozen and not c.deadline_stats['student_default']
