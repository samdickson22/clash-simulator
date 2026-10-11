"""X4S2 scaling-charge tests (exploration only)."""
import time
from run import make_charger, scaled_deadline


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


def test_scaled_deadline_models_slow_cancellable_step():
    assert scaled_deadline(None, 1.0, 2.) is None
    # 100 ms left at half speed: the step may use 50 ms of fleet time; charging its duration ends at the cutoff.
    d = scaled_deadline(1.1, 1.0, 2.)
    assert abs(d-1.05) < 1e-12 and abs(1.0+(d-1.0)*2.-1.1) < 1e-12
    assert scaled_deadline(1.0, 1.0, 1.5) == 1.0
    assert scaled_deadline(0.9, 1.0, 2.) < 1.0  # already past the cutoff: immediate timeout


def test_prep_sequence_charges_each_duration_once():
    # Mirrors run_game's prep path: pre-belief, belief (scaled deadline), candidates, sample+root.
    now = [0.]
    def sleep(x): now[0] += x
    clock = lambda: now[0]
    scale, cutoff = 2., .112
    charge, total = make_charger(scale, sleep=sleep, clock=clock)
    slept = 0.
    now[0] += .010; slept += charge(clock()-0.)            # observation+poll: 10 ms -> +10 ms
    b0 = clock(); assert abs(scaled_deadline(cutoff, b0, scale)-(b0+(cutoff-b0)/2)) < 1e-12
    now[0] += .004; slept += charge(clock()-b0)            # belief 4 ms -> +4 ms
    c0 = clock(); now[0] += .006; slept += charge(clock()-c0)  # candidates 6 ms -> +6 ms
    assert abs(slept-.020) < 1e-12 and abs(clock()-.040) < 1e-12 and total[1] == 3
