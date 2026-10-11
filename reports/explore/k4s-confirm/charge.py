"""PREREG-K4S honest inference charge (r3 §2.4), ported from reports/explore/x4s2/run.py make_charger.

Every arm at cell c sleeps an extra (1/c - 1) x the measured poll_seconds of the search seat's
network poll in each search decision, inside the decision timer. At c = 1 it never sleeps.
The sleep idles the slot's dedicated core and only shifts the deadline.
"""
import time


def make_charger(scale, sleep=time.sleep, clock=time.monotonic):
    """Emulate (scale-1)*seconds of extra work on a 1/scale-speed core (wall sleep inside the timer)."""
    total = [0., 0]
    def charge(seconds):
        extra = (scale-1.)*seconds
        if extra <= 0: return 0.
        t = clock(); sleep(extra); slept = clock()-t
        total[0] += slept; total[1] += 1
        return slept
    return charge, total
