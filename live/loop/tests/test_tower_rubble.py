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
# revival (s72-m03 / s69-m12 opp-left: a living princess's number unreadable for 60 frames, then read again)
lost = [2030]*3 + [426]*3 + [None]*70 + [342]*5
a = run(lost)
check('a princess declared dead revives on 2 real readings at or below its last HP', (False in a) and a[-1] is True)
# rubble showing deploy-text 'lvl.' misread as 11 / 111 (s67-m06, s69-m12 own-left, Sol 10-17) must not revive
fake = [2030]*3 + [240]*3 + [None]*70 + [111, 111, 11, 11, 111, None, 1, 1]
check("all-1s readings ('11', '111') never revive a destroyed princess", run(fake)[-1] is False)
# a number above the last HP (another tower's / a damage number) does not revive
above = [2030]*3 + [300]*8 + [None]*70 + [1500, 1500, 1500]   # 8 reads: a big drop needs 6 identical to be accepted
check('readings above the last HP do not revive', run(above)[-1] is False)
# guard_towers lets a revived tower out of its dead latch, but keeps an unrevived one dead
last = {}
T.guard_towers({'towers': [dict(owner=1, kind='princess', side='right', alive=False, hp_frac=0.)]}, last)
r1 = {'towers': [dict(owner=1, kind='princess', side='right', alive=True, hp_frac=.1)]}
T.guard_towers(r1, last)
r2 = {'towers': [dict(owner=1, kind='princess', side='right', alive=True, hp_frac=.1, revived=True)]}
T.guard_towers(r2, last)
pick = lambda r: [t for t in r['towers'] if t['owner'] == 1 and t['side'] == 'right' and t['kind'] == 'princess'][0]['alive']
check('guard_towers: dead stays dead without revival, revived tower passes the latch', pick(r1) is False and pick(r2) is True)
# unread: frames since the last real reading, on all 6 slots after apply + guard_towers, incl. a slot perception dropped
reads = [2030]*3 + [None]*5 + [2000]*2 + [None]*3
seq = iter(reads); orig = T.read_number
T.read_number = lambda f, box: next(seq) if box == T.BOX[('own', 'left')] else None
try:
    rd, last, got, slots, carried = T.TowerReader(), {}, [], [], []
    for i in range(len(reads)):
        towers = [dict(owner=o, kind=k, side=sd, alive=True, hp_frac=1., score=1.) for o, k, sd in T.SLOTS]
        if i >= 9:                                       # perception drops our left princess for the last frames
            towers = [t for t in towers if not (t['owner'] == 0 and t['side'] == 'left' and t['kind'] == 'princess')]
        rec = {'towers': towers}
        rd.apply(rec, None); T.guard_towers(rec, last)
        own_l = [t for t in rec['towers'] if t['owner'] == 0 and t['kind'] == 'princess' and t['side'] == 'left'][0]
        got.append(own_l['unread']); slots.append(all('unread' in t for t in rec['towers'])); carried.append(own_l.get('carried', False))
        assert '_tower_unread' not in rec
finally:
    T.read_number = orig
check('unread counts frames since the last real reading and resets on a reading', got[:10] == [0, 0, 0, 1, 2, 3, 4, 5, 0, 0])
check('unread is on all 6 slots and follows the reader on a carried slot', all(slots) and carried[-1] and got[-3:] == [1, 2, 3])
plain = {'towers': [dict(owner=1, kind='princess', side='left', alive=True, hp_frac=1.)]}
T.guard_towers(plain, {})
check('guard_towers without apply adds no unread field', all('unread' not in t for t in plain['towers']))
# touching digits: '305' (s73-m14 enemy-left; the '3' touches a wide '0') must be cut at the gap between them, not at w/2
import cv2
FX = Path(__file__).resolve().parent/'fixtures'
for name, want in (('tower-num-s73m14-800-305.png', 305), ('tower-num-s73m14-764-824.png', 824)):
    crop = cv2.imread(str(FX/name))
    check(f'touching digits read: {name} -> {want}', T.read_number(crop, (0, 0, crop.shape[1], crop.shape[0])) == want)
print(f'{passed} passed, {failed} failed'); sys.exit(1 if failed else 0)
