"""PREREG-K4S END reference/pool logic tests (no torch, no corpus)."""
from fractions import Fraction
import pytest
from end_reference import Timed, charge_scale, CELLS
from end_pool import pool


def test_charge_scale_strings():
    assert [charge_scale(c) for c, _ in CELLS] == ['1', '10/9', '5/4', '10/7', '5/3']


def test_timed_records_pure_poll_and_charges_inside():
    now = [0.]
    class P:
        def sample(self, *a): now[0] += .010; return 7
        def propose(self, *a): return 'p'
    def sleep(x): now[0] += x
    t = Timed(P(), sleep=sleep, clock=lambda: now[0])
    assert t.sample() == 7 and t.last_poll == pytest.approx(.010) and t.last_sleep == 0. and t.propose() == 'p'
    t.scale = Fraction(5, 3); t.sample()
    assert t.last_poll == pytest.approx(.010) and t.last_sleep == pytest.approx(.010*2/3)
    assert t.last_sleep/(t.last_poll+t.last_sleep) == pytest.approx(1-3/5)


def raw(host, factor, ids=('a', 'b', 'c')):
    states = {i: dict(k4_wall=[.1*factor]*3, k4s_wall=[.1*factor*(1+k/100) for k in range(3)], sd1_poll=[.01]*3, v1_poll=[.012]*3,
                      result=dict(action=1, candidates=[1, 2304], scores=[.5, .4])) for i in ids}
    dl = {str(float(c)): dict(budget_ms=b, charge_scale=charge_scale(c), rows=[dict(id=i, repeat=r, cutoff=r == 0, no_complete_play=False, fallback=False)
                                                                              for i in ids for r in range(3)]) for c, b in CELLS}
    return dict(host=host, corpus_sha256='x', repeats=3, states=states, deadline=dl)


def test_pool_conforms_and_counts():
    out = pool([raw('127x01', 1.0), raw('127x03', 1.02)])
    assert out['pool_conforms'] and out['deadline']['0.8']['n'] == 18 and out['deadline']['0.8']['cutoff_count'] == 6
    assert out['deadline']['0.6']['charge_scale'] == '5/3' and out['schema'] == 'clasher.k4s.mac-fleet-reference.v1'


def test_pool_fails_closed_outside_window():
    out = pool([raw('127x01', 1.0), raw('127x03', 1.2)])
    assert not out['pool_conforms']


def test_pool_rejects_missing_state_and_inexact_result():
    with pytest.raises(AssertionError): pool([raw('127x01', 1.0), raw('127x03', 1.0, ids=('a', 'b'))])
    bad = raw('127x03', 1.0); bad['states']['a']['result'] = dict(action=2, candidates=[2], scores=[1.])
    with pytest.raises(AssertionError): pool([raw('127x01', 1.0), bad])
