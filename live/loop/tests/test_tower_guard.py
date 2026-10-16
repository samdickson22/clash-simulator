"""towers.guard_towers: always 6 towers; a missing slot carries its last state; dead stays dead.
   python tests/test_tower_guard.py   (exit 0 = all pass)"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import towers as TW  # noqa: E402


def rec(towers):
    return dict(towers=copy.deepcopy(towers))


def T(owner, kind, side, alive=True, hp=1.0):
    return dict(owner=owner, kind=kind, side=side, alive=alive, hp_frac=hp, score=.9)


FULL = [T(o, k, s) for o, k, s in TW.SLOTS]
checks = []


def check(name, cond):
    checks.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name)


last = {}
r = rec(FULL)
check('full record: 0 missing', TW.guard_towers(r, last) == 0)
check('full record: 6 towers, unchanged order of slots', [(t['owner'], t['kind'], t['side']) for t in r['towers']] == TW.SLOTS)

# frame 2: opponent left princess destroyed (reported dead)
dead = [T(1, 'princess', 'left', alive=False, hp=0.)] + [t for t in FULL if (t['owner'], t['side']) != (1, 'left')]
r = rec(dead)
check('dead report: 0 missing', TW.guard_towers(r, last) == 0)
# frame 3: that tower drops out of the record entirely
r = rec([t for t in FULL if not (t['owner'] == 1 and t['side'] == 'left' and t['kind'] == 'princess')])
n = TW.guard_towers(r, last)
opp_left = [t for t in r['towers'] if (t['owner'], t['kind'], t['side']) == (1, 'princess', 'left')]
check('missing slot counted', n == 1)
check('missing dead tower carried as dead (pocket stays open)', len(opp_left) == 1 and opp_left[0]['alive'] is False
      and opp_left[0]['hp_frac'] == 0. and opp_left[0].get('carried'))
check('still 6 towers', len(r['towers']) == 6)
# frame 4: a misread says it is alive again -> stays dead
r = rec(FULL)
TW.guard_towers(r, last)
opp_left = [t for t in r['towers'] if (t['owner'], t['kind'], t['side']) == (1, 'princess', 'left')][0]
check('dead stays dead against an alive misread', opp_left['alive'] is False and opp_left['hp_frac'] == 0.)
# a slot never seen and missing: default alive at full HP, carried
last2 = {}
r = rec([t for t in FULL if t['kind'] != 'king'])
check('two kings missing on the first frame', TW.guard_towers(r, last2) == 2)
kings = [t for t in r['towers'] if t['kind'] == 'king']
check('never-seen missing slot defaults alive/1.0 and is marked carried', len(kings) == 2 and all(
    k['alive'] and k['hp_frac'] == 1.0 and k['carried'] for k in kings))
# damaged HP is carried as last seen
last3 = {}
TW.guard_towers(rec([T(1, 'king', 'center', hp=.4)] + [t for t in FULL if not (t['owner'] == 1 and t['kind'] == 'king')]), last3)
r = rec([t for t in FULL if not (t['owner'] == 1 and t['kind'] == 'king')])
TW.guard_towers(r, last3)
k = [t for t in r['towers'] if (t['owner'], t['kind']) == (1, 'king')][0]
check('missing damaged tower carries its last HP', k['hp_frac'] == .4 and k['alive'])
print(f"{sum(c for _, c in checks)} passed, {sum(not c for _, c in checks)} failed")
sys.exit(0 if all(c for _, c in checks) else 1)
