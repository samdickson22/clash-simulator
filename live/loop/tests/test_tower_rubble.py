"""A destroyed princess's rubble reads stray single digits and blinking 0/1: they must not keep the tower alive
(s60-m02: 3 HP, then rubble, declared dead 13 s late). Real numbers still restart the death clock. Script: python test_tower_rubble.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import towers as T

passed = failed = 0


def check(name, ok):
    global passed, failed
    print(('PASS ' if ok else 'FAIL ') + name); passed += ok; failed += not ok


def run(reads, key=('own', 'left')):
    """reads: per-frame read_number value for `key` (others None) -> list of alive flags."""
    seq = iter(reads); orig = T.read_number
    T.read_number = lambda f, box: next(seq) if box == T.BOX[key] else None
    try:
        r = T.TowerReader(); out = []
        for _ in reads:
            out.append(r.update(None)[key][0])
        return out
    finally:
        T.read_number = orig


# full tower, falls to 3 HP, then rubble: stray '3'/'5'/'7' and blinking 0/1 every few frames
rubble = [2030]*3 + [135]*3 + [3]*3 + ([None, None, 5, None, 0, None, 7, None, 1, 3] * 12)
a = run(rubble)
first_dead = a.index(False) if False in a else None
check('rubble digits do not keep a dead tower alive (dead within 60 frames of the last real number)', first_dead is not None and first_dead <= 9 + 60)
# a living tower whose number blinks / is partly occluded (leading digit missed) keeps living
alive = [2030]*3 + ([900, None, 0, 90, None, 899, None, None, 1, 898] * 12)
check('a damaged tower with blinking, partly occluded numbers stays alive', all(run(alive)))
# a tower really at 3 HP that keeps showing 3 stays alive
check('a tower really at 3 HP showing 3 stays alive', all(run([2030]*3 + [135]*3 + [3]*90)))
print(f'{passed} passed, {failed} failed'); sys.exit(1 if failed else 0)
