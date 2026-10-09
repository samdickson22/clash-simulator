"""Deterministic cutoff, whole-root admission, frozen W scores and epsilon ties."""
from types import SimpleNamespace
import pytest
from planner import anytime

class Clock:
    def __init__(self): self.now = 0.
    def __call__(self): return self.now


def core(arm='W'):
    return SimpleNamespace(arm=arm, info=SimpleNamespace(packet=SimpleNamespace(
        observation=SimpleNamespace(global_features=[0]*5+[.5]))))


def scorer(cost=.01, values=None):
    clock = Clock(); calls = []
    def evaluate(a, style, remaining):
        calls.append((a, style)); clock.now += cost
        return (values or {}).get((a, style), a/10000)
    return clock, calls, evaluate


def test_zero_budget_policy_fallback():
    c = core(); clock, calls, evaluate = scorer()
    assert anytime(c, None, 0, [1,2304,2400,2401,2402], 0., 7, clock=clock, evaluate=evaluate) == 7
    assert calls == [] and c.deadline_stats == dict(hit=True, fallback=True, completed=0, candidates=5)


def test_late_coarse_scan_is_not_scored():
    c = core(); clock, calls, evaluate = scorer(.1)
    assert anytime(c, None, 0, [1,2,2304,2400], .2, 7, clock=clock, evaluate=evaluate) == 7
    assert len(calls) == 2 and c.deadline_stats['completed'] == 0


def test_partial_root_discarded_best_complete_kept():
    c = core('0'); clock, calls, evaluate = scorer(.05, {(1,s):1. for s in ('balanced','pressure','defense')})
    assert anytime(c, None, 0, [1,2,2304], .25, 7, clock=clock, evaluate=evaluate) == 1
    assert c.last['scores'] == [1., None, None] and not c.deadline_stats['fallback']


def test_wait10_reused_before_later_timeout():
    c = core(); clock, calls, evaluate = scorer(.05)
    assert anytime(c, None, 0, [2304,2400,2401,2402], .2, 7, clock=clock, evaluate=evaluate) == 2304
    assert c.last['scores'][0] == c.last['scores'][1]
    assert c.last['scores'][2:] == [None,None] and len(calls) == 4


def test_full_w_reduction_order_and_tie():
    c = core(); clock, calls, evaluate = scorer(.001, {(a,s):1. for a in range(12) for s in ('balanced','pressure','defense')})
    candidates = list(range(12))+[2304,2400,2401,2402]
    assert anytime(c, None, 0, candidates, 10., 7, clock=clock, evaluate=evaluate) == 0
    assert c.last['candidates'] == list(range(8))+[2304,2400,2401,2402]
    assert not c.deadline_stats['hit'] and not c.deadline_stats['fallback']
    assert [a for a,s in calls[:12]] == list(range(12))
    assert sum(a==2400 for a,s in calls) == 0


def test_native_timeout_and_repeated_clock_determinism():
    records=[]
    for _ in range(2):
        c=core('0'); clock=Clock()
        def evaluate(a,s,r): raise TimeoutError('native tick cutoff')
        action=anytime(c,None,0,[1,2304],.2,9,clock=clock,evaluate=evaluate)
        records.append((action,c.last,c.deadline_stats))
    assert records[0] == records[1] and records[0][0] == 9
