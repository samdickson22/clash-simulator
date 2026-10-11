"""PREREG-K4S charge tests, ported from reports/explore/x4s2/test_charge.py (poll mode only; the
X4S2 prep-mode scaled-deadline tests are not ported because K4S has no prep mode)."""
import time
from charge import make_charger


def test_unscaled_never_sleeps():
    calls = []
    charge, total = make_charger(1.0, sleep=calls.append)
    assert charge(.010) == 0. and calls == [] and total == [0., 0]


def test_charge_sleeps_scale_minus_one_and_accumulates():
    now = [0.]
    def sleep(x): now[0] += x
    charge, total = make_charger(200/140, sleep=sleep, clock=lambda: now[0])
    a = charge(.010); b = charge(.004)
    assert abs(a-.010*(200/140-1)) < 1e-12 and abs(b-.004*(200/140-1)) < 1e-12
    assert total[1] == 2 and abs(total[0]-(a+b)) < 1e-12
    assert charge(0.) == 0. and charge(-1.) == 0. and total[1] == 2


def test_real_sleep_covers_requested_extra():
    charge, total = make_charger(2.0)
    t = time.monotonic(); slept = charge(.005); wall = time.monotonic()-t
    assert .005 <= slept <= wall < .05


def test_share_formula_every_cell():
    # Sleep share of the charged poll span is (1/c - 1)/(1/c) = 1 - c (r3 §4.1 charge test).
    for b in (200, 180, 160, 140, 120):
        now = [0.]
        def sleep(x): now[0] += x
        charge, _ = make_charger(200/b, sleep=sleep, clock=lambda: now[0])
        poll = .010; slept = charge(poll)
        assert abs(slept/(poll+slept) - (1-b/200)) < 1e-12
