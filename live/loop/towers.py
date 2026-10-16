"""Tower HP from the numbers the official client draws over each tower (16:9 layout, Android px).

Digits: bright, low-saturation connected components in a fixed box per tower, classified by the nearest of 28
k-means centroids (12x18) labelled once from recorded frames (digits.npz; 'x' = not a digit). Max HP: the princess's
first full reading gives the tower level (clasher/tower_scaling.py growth: King HP +7%/level, others +8%, +10% from
level 10); the king's max is that level's King HP (its number is hidden until damaged). A tower's HP is the latest reading
confirmed by the previous non-empty reading within 10 frames (equal, or falling within (cur/2, cur]); a rise or a drop
by more than half needs 6 identical readings (a misread '2' for 280 latched under a running minimum in live3; numbers
blink under hits, so consecutive-frame equality went stale in live8). A princess whose number is gone for 60
healthy frames (the driver skips dimmed/black frames) is destroyed for good; the king stays alive (its death ends the match).
"""
from pathlib import Path

import cv2
import numpy as np

BOX = {('opp', 'king'): (480, 20, 720, 70), ('opp', 'left'): (205, 250, 340, 292), ('opp', 'right'): (770, 250, 905, 292),
       ('own', 'left'): (205, 1180, 340, 1225), ('own', 'right'): (770, 1180, 905, 1225), ('own', 'king'): (420, 1455, 700, 1505)}
_D = np.load(Path(__file__).resolve().parent/'digits.npz')
CENT, LABS = _D['centroids'], _D['labels']


def tower_hp(kind, level):
    base, growth = (2400, 7) if kind == 'king' else (1400, 8)
    pct = 100
    for lv in range(2, level + 1):
        pct = pct*(100 + (growth if lv <= 9 else 10))//100
    return base*pct//100


def level_of_princess(hp):
    return min(range(1, 16), key=lambda lv: abs(tower_hp('princess', lv) - hp))


def read_number(f, box):
    x1, y1, x2, y2 = box
    c = f[y1:y2, x1:x2].astype(np.int16)
    g = .299*c[..., 2] + .587*c[..., 1] + .114*c[..., 0]
    m = ((g > 185) & ((c.max(2) - c.min(2)) < 110)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    gl = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if not (13 <= h <= 32 and 3 <= w and a >= 25):
            continue
        # touching digits form one wide component (live8: '84' of 840 -> read '0'): split at the digit width (~0.72 h)
        k = max(1, int(round(w/(.72*h)))) if w > 26 else 1
        if w/k > 26:
            continue
        comp = (lab[y:y+h, x:x+w] == i).astype(np.float32)
        for j in range(k):
            xa, xb = int(round(j*w/k)), int(round((j + 1)*w/k))
            v = cv2.resize(comp[:, xa:xb], (12, 18), interpolation=cv2.INTER_AREA).ravel()
            d = ((CENT - v)**2).sum(1)
            ch = LABS[int(np.argmin(d))]
            # a poor template match is not a digit (bright tower stones on the Bone Pit sand read as king HP '3'/'31'/'32'
            # and the bot spelled a full-HP king, s1 battle 1); recorded
            # digits match within ~15 (max 71 of 271), the stones at >= 37
            gl.append((x + xa, y + h, h, ch if ch != 'x' and d.min() <= 30 else None))
    gl.sort()
    good = [g for g in gl if g[3] is not None]
    if not good:
        return None
    base = np.median([b for _, b, _, _ in good]); hh = np.median([h for _, _, h, _ in good])
    row = [g for g in gl if abs(g[1] - base) <= 4 and abs(g[2] - hh) <= 5]
    if any(ch is None for *_, ch in row):
        return None                 # a non-digit blob in the number's row: unreadable, not a shorter number
    digits = [ch for *_, ch in row]
    return int(''.join(digits)) if 1 <= len(digits) <= 5 else None


class TowerReader:
    def __init__(self):
        self.hp, self.prev, self.missing, self.dead, self.level = {}, {}, {}, set(), {'opp': None, 'own': None}

    def update(self, f):
        """f: Android-size BGR frame -> {(side, kind): (alive, hp, max_hp)}."""
        out = {}
        for key, box in BOX.items():
            side, kind = key
            v = read_number(f, box)
            if kind != 'king' and v is not None and self.level[side] is None and v in {tower_hp('princess', l) for l in range(1, 16)}:
                self.level[side] = level_of_princess(v)
            zero = v in (0, 1)                # a flashing number reads '0', a falling level badge '1': present, not a value
            if zero:
                v = None
            hist = (self.prev.get(key, ()) + (v,))[-10:]
            self.prev[key] = hist
            cur = self.hp.get(key)
            vals = [h for h in hist if h is not None]          # numbers blink under hits: confirm on actual readings
            if v is not None:
                if cur is None or cur/2 <= v <= cur:
                    if len(vals) >= 2 and cur is None and vals[-2] == v or len(vals) >= 2 and cur is not None and v <= vals[-2] <= cur:
                        self.hp[key] = v                        # two readings agree / keep falling within range
                elif len(vals) >= 6 and len(set(vals[-6:])) == 1:
                    self.hp[key] = v                            # big drop or rise: 6 identical readings
            self.missing[key] = 0 if v is not None or zero else self.missing.get(key, 0) + 1
            if kind != 'king' and self.missing[key] >= 60:
                self.dead.add(key)
            lv = self.level[side] or self.level['opp' if side == 'own' else 'own'] or 1
            mx = tower_hp(kind, lv)
            hp = min(self.hp.get(key, mx), mx)
            alive = key not in self.dead
            out[key] = (alive, hp if alive else 0, mx)
        return out

    def apply(self, rec, f):
        """Overwrite rec['towers'] alive/hp_frac from the numbers (owner 0 = own, 1 = opp; side left/right/center)."""
        r = self.update(f)
        for t in rec['towers']:
            key = ('own' if t['owner'] == 0 else 'opp', 'king' if t['kind'] == 'king' else t['side'])
            alive, hp, mx = r[key]
            t['alive'], t['hp_frac'], t['hp_read'] = alive, round(hp/mx, 4) if alive else 0., hp
        return r


SLOTS = [(o, k, s) for o in (0, 1) for k, s in (('king', 'center'), ('princess', 'left'), ('princess', 'right'))]


def guard_towers(rec, last):
    """Always 6 towers in rec['towers']: a slot missing from the record (perception/OCR) is filled with its last known
    state, and a tower once dead stays dead (bot/live/translate.py treats a missing tower as alive at 100%: a destroyed
    tower dropping out would close the pocket and drop the crown from the evaluation). `last` (dict, per battle) keeps
    the state. Returns the number of slots filled this frame."""
    have = {(t['owner'], t['kind'], t['side']): t for t in rec.get('towers', ())}
    out, missing = [], 0
    for key in SLOTS:
        t = have.get(key)
        prev = last.get(key)
        if t is None:
            missing += 1
            t = dict(prev) if prev else dict(owner=key[0], kind=key[1], side=key[2], alive=True, hp_frac=1.0, score=0.0)
            t['carried'] = True
        elif prev is not None and not prev['alive'] and t.get('alive'):
            t = dict(t, alive=False, hp_frac=0.0, hp_read=0)            # dead stays dead
        last[key] = {k: v for k, v in t.items() if k != 'carried'}
        out.append(t)
    rec['towers'] = out
    return missing
