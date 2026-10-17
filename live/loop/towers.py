"""Tower HP from the numbers the official client draws over each tower (16:9 layout, Android px).

Digits: bright, low-saturation connected components in a fixed box per tower, classified by the nearest of 28
k-means centroids (12x18) labelled once from recorded frames (digits.npz; 'x' = not a digit). Max HP: the princess's
first full reading gives the tower level (clasher/tower_scaling.py growth: King HP +7%/level, others +8%, +10% from
level 10); the king's max is that level's King HP (its number is hidden until damaged, so a king STARTS FULL: its first reading
must be >= max/2 with two agreeing reads; no 6-identical bypass). A tower's HP is the latest reading
confirmed by the previous non-empty reading within 10 frames (equal, or falling within (cur/2, cur]); a rise or a drop
by more than half needs 6 identical readings (a misread '2' for 280 latched under a running minimum in live3; numbers
blink under hits, so consecutive-frame equality went stale in live8). A princess without a real HP number for 60 healthy frames
(the driver skips dimmed/black frames; rubble's stray single digits and blinking '0'/'1' do not count) is destroyed for good;
the king stays alive (its death ends the match).

Troop-level badges are excluded from HP numbers; rejected components stay unreadable so they cannot shorten a number.
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


BADGE_RED = .4


def badge_ring(c, comp, x, y, w, h, pad=4):
    """Fraction of saturated-red pixels in a 4 px ring around a digit component (c: BGR int16 crop; comp: its mask).
    Troop level badges are a white digit on a filled red square; tower HP numbers are outlined white text."""
    Y0, Y1, X0, X1 = max(0, y - pad), min(c.shape[0], y + h + pad), max(0, x - pad), min(c.shape[1], x + w + pad)
    sub, m = c[Y0:Y1, X0:X1], comp[Y0:Y1, X0:X1].astype(np.uint8)
    ring = ~cv2.dilate(m, np.ones((3, 3), np.uint8)).astype(bool)
    b, g, r = sub[..., 0], sub[..., 1], sub[..., 2]
    red = (r > 110) & (r > 2.5*g) & (r > 1.8*b)
    # A red HP bar UNDER a real digit is not a surrounding badge. Require red above the digit too; use the
    # normalized live pixels, since uniform gain changes the absolute red thresholds as well as digit geometry.
    top = red[:max(0, y - Y0), :]
    bottom = red[y + h - Y0:, :]
    score = min(float(red[ring].mean()), float(top.mean()), float(bottom.mean())) if ring.any() and top.size and bottom.size else 0.
    if score <= BADGE_RED:
        return 0.
    # The red must form one compact surrounding square, rather than a wide HP bar or the king tower's roof.
    rb, gb, bb = c[..., 2], c[..., 1], c[..., 0]
    red_all = ((rb > 110) & (rb > 2.5*gb) & (rb > 1.8*bb)).astype(np.uint8)
    _, _, regions, _ = cv2.connectedComponentsWithStats(red_all)
    for rx, ry, rw, rh, _ in regions[1:]:
        if (rx < x and ry < y and rx + rw > x + w and ry + rh > y + h
                and rw <= w + 52 and rh <= h + 16):
            return score
    return 0.


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
        badge = badge_ring(c, lab == i, x, y, w, h) > BADGE_RED
        comp = (lab[y:y+h, x:x+w] == i).astype(np.float32)
        # cut touching digits at the column-sum valley near each equal-width boundary, not at the boundary itself: a '3'
        # touching a wide '0' ('305', s73-m14 enemy-left: unreadable for 21 s, declared dead at 305 HP) cut at w/2 gave
        # the '3' a slice of the '0' (template distance 37 > 30 -> None); the valley cut reads 3 (7) and 0 (16)
        cuts, col = [0], comp.sum(0)
        for j in range(1, k):
            c0 = int(round(j*w/k)); r = max(1, int(round(.3*w/k)))
            lo, hi = max(cuts[-1] + 3, c0 - r), min(w - 3, c0 + r)
            cuts.append(lo + int(np.argmin(col[lo:hi + 1])) if hi >= lo else c0)
        cuts.append(w)
        for j in range(k):
            xa, xb = cuts[j], cuts[j + 1]
            v = cv2.resize(comp[:, xa:xb], (12, 18), interpolation=cv2.INTER_AREA).ravel()
            d = ((CENT - v)**2).sum(1)
            ch = LABS[int(np.argmin(d))]
            # a poor template match is not a digit (bright tower stones on the Bone Pit sand read as king HP '3'/'31'/'32'
            # and the bot spelled a full-HP king, s1 battle 1); recorded
            # digits match within ~15 (max 71 of 271), the stones at >= 37
            gl.append((x + xa, y + h, h, ch if not badge and ch != 'x' and d.min() <= 30 else None))
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


REVIVE_N = 2          # consecutive real readings that revive a princess declared dead
# Badge intrusion (s76-m13 own-right: an enemy goblin's red level badge crossed our HP text; its '7' and the exposed digits read
# as 274 / 176 and were accepted). A detected unit's level-badge region (the badge v2b crop spec: width max(w+16,48) centred, from
# 30 px above the box top to 10 px below, in 720-wide px; x1.5 here) covering >= OCC_FRAC of a princess HP box means that frame's
# number-like read below half the current HP is not an HP value: it neither updates the HP nor votes for a revival. The
# death clock is unchanged (a visible number keeps the tower alive, as before): census gates s60-s78 (159 runs) - a blanket pause
# delayed ~50 deaths by up to 27 frames, discarding covered reads killed s76-m13 own-right early, and a pause bounded at 30 still
# did (a real 1287 -> 177 drop under a badge, 1470-1474). OCC_FRAC from census s68-s73 (391k labelled frames): .40 flags .16% of
# clean reads; every frame of the m13 badge pass (776-828) overlaps .60-.73.
OCC_FRAC = .40


def badge_regions(rec):
    """Level-badge regions (Android px) of every detected unit in a perception record (units_yolo_info / unknown_yolo_info boxes)."""
    out = []
    for k in ('units_yolo_info', 'unknown_yolo_info'):
        for e in rec.get(k) or ():
            b = e.get('box') if isinstance(e, dict) else None
            if b and len(b) == 4:
                x1, y1, x2, y2 = b; w = max(x2 - x1 + 24, 72); cx = (x1 + x2)/2
                out.append((cx - w/2, y1 - 45, cx + w/2, y1 + 15))
    return out


def occluded_keys(regions, frac=OCC_FRAC):
    """Princess HP boxes covered >= frac by any badge region."""
    keys = set()
    for key, (x1, y1, x2, y2) in BOX.items():
        if key[1] == 'king':
            continue
        area = (x2 - x1)*(y2 - y1)
        for a, b, c, d in regions:
            if max(0., min(x2, c) - max(x1, a))*max(0., min(y2, d) - max(y1, b)) >= frac*area:
                keys.add(key); break
    return keys


class TowerReader:
    def __init__(self):
        self.hp, self.prev, self.missing, self.dead, self.level = {}, {}, {}, set(), {'opp': None, 'own': None}
        self.revive = {}                # dead princess: consecutive real readings at or below its last HP (revival evidence)
        self.revived = set()            # princesses revived this battle (guard_towers lets them out of its dead latch)

    def update(self, f, occluded=frozenset()):
        """f: Android-size BGR frame -> {(side, kind): (alive, hp, max_hp)}. occluded: princess keys whose HP number a unit's
        level badge covers this frame (occluded_keys): an implausible number there is not an HP value (death clock unchanged)."""
        out = {}
        for key, box in BOX.items():
            side, kind = key
            occ = key in occluded
            v = read_number(f, box)
            # under a unit badge a number-like read far below the current HP (s76-m13: 274 / 176 for a 2184 tower) is the badge's
            # digit + exposed digits: no HP update and no revival vote, but the death clock restarts as for any number >= 10
            # (deployed behaviour). Plausible reads (cur/2..cur) count as usual; None / stray digits too, so rubble dies on time.
            # Reads ABOVE the current HP are not masked: they correct an earlier bad latch (s78-m01 opp-right 211 -> 2114, s69-m11
            # 17 -> 2184, Sol video 10-17) and a rise still needs 6 identical readings.
            cur0 = self.hp.get(key, tower_hp(kind, self.level[side] or self.level['opp' if side == 'own' else 'own'] or 1) if kind == 'king' else None)
            masked = (occ and v is not None and v >= 10 and set(str(v)) != {'1'}
                      and cur0 is not None and v < cur0/2)
            if masked:
                v = None
            if kind != 'king' and v is not None and self.level[side] is None and v in {tower_hp('princess', l) for l in range(1, 16)}:
                self.level[side] = level_of_princess(v)
            zero = v in (0, 1)                # a flashing number reads '0', a falling level badge '1': present, not a value
            if zero:
                v = None
            hist = (self.prev.get(key, ()) + (v,))[-10:]
            self.prev[key] = hist
            lv = self.level[side] or self.level['opp' if side == 'own' else 'own'] or 1
            mx = tower_hp(kind, lv)
            cur = self.hp.get(key)
            if kind == 'king' and cur is None:
                # the king's number is hidden until its first damage, so its true starting state is FULL (not unknown): its first
                # reading must be a plausible fall from max, >= max/2 with two agreeing reads (no 6-identical bypass). runs-all
                # 2026-10-16: all 80 genuine first king readings were >= .837 of max; all 6 false ones <= .002 (stray badge/stone
                # reads latched as e.g. 5 HP, then Fireballs on a full king: s1-m01 s8-m02 s28-m02 s28-m03 s29-m02 s38-m01)
                cur = mx
            vals = [h for h in hist if h is not None]          # numbers blink under hits: confirm on actual readings
            if v is not None:
                if cur is None or cur/2 <= v <= cur:
                    if len(vals) >= 2 and cur is None and vals[-2] == v or len(vals) >= 2 and cur is not None and v <= vals[-2] <= cur:
                        self.hp[key] = v                        # two readings agree / keep falling within range
                elif len(vals) >= 6 and len(set(vals[-6:])) == 1 and not (kind == 'king' and key not in self.hp):
                    self.hp[key] = v                            # big drop or rise: 6 identical readings (not a king's FIRST reading)
            # the death clock restarts only on a real HP number: >= 10, or a single digit that is the current HP itself (a tower at
            # 3 HP). A destroyed princess's rubble reads stray single digits ('3'-'7') and blinking '0'/'1' for minutes, which used
            # to keep it alive (s60-m02: 13 s, the bot rejected the opponent's pocket deploy; runs-all s30-s61: death p90 103 -> 60
            # frames, max 369 -> 220, no new early death)
            real = masked or v is not None and (v >= 10 or (cur is not None and cur/2 <= v <= cur))
            self.missing[key] = 0 if real else self.missing.get(key, 0) + 1
            if kind != 'king' and self.missing[key] >= 60:
                self.dead.add(key)
            # Revival: a princess declared dead that shows REVIVE_N consecutive real readings (>= 10, at or below its last
            # HP) was not destroyed: its number was unreadable for 60 frames (s72-m03: a living princess at 342 HP read as
            # dead from tick 549 to the end). Rubble only reads stray single digits / blinking 0-1, never >= 10.
            if key in self.dead:
                last = self.hp.get(key, mx)
                # all-1s numbers ('11', '111') are deploy-text "lvl." over rubble (Sol 10-17, s67-m06 / s69-m12), not HP
                ok = v is not None and v >= 10 and v <= last and set(str(v)) != {'1'}
                if not masked:
                    self.revive[key] = self.revive.get(key, 0) + 1 if ok else 0
                if self.revive.get(key, 0) >= REVIVE_N:
                    self.dead.discard(key); self.missing[key] = 0; self.revive[key] = 0
                    self.hp[key] = v; self.revived.add(key)
            hp = min(self.hp.get(key, mx), mx)
            alive = key not in self.dead
            out[key] = (alive, hp if alive else 0, mx)
        return out

    def apply(self, rec, f):
        """Overwrite rec['towers'] alive/hp_frac from the numbers (owner 0 = own, 1 = opp; side left/right/center)."""
        r = self.update(f, occluded_keys(badge_regions(rec)))
        for t in rec['towers']:
            key = ('own' if t['owner'] == 0 else 'opp', 'king' if t['kind'] == 'king' else t['side'])
            alive, hp, mx = r[key]
            t['alive'], t['hp_frac'], t['hp_read'] = alive, round(hp/mx, 4) if alive else 0., hp
            if alive and key in self.revived:
                t['revived'] = True
        # frames since each tower's last real HP reading (0 = read this frame), for all 6 slots: guard_towers writes it on
        # every slot incl. ones it carries, so a princess that fell and dropped out of perception still shows the count
        # (translator births: P(our princess is down) from hp_read + unread; the reader declares death at 60)
        rec['_tower_unread'] = {f"{0 if side == 'own' else 1}/{'king' if kind == 'king' else 'princess'}/"
                                f"{'center' if kind == 'king' else kind}": self.missing.get((side, kind), 0) for side, kind in r}
        return r


SLOTS = [(o, k, s) for o in (0, 1) for k, s in (('king', 'center'), ('princess', 'left'), ('princess', 'right'))]


def guard_towers(rec, last):
    """Always 6 towers in rec['towers']: a slot missing from the record (perception/OCR) is filled with its last known
    state, and a tower once dead stays dead (bot/live/translate.py treats a missing tower as alive at 100%: a destroyed
    tower dropping out would close the pocket and drop the crown from the evaluation). `last` (dict, per battle) keeps
    the state. Returns the number of slots filled this frame."""
    have = {(t['owner'], t['kind'], t['side']): t for t in rec.get('towers', ())}
    unread = rec.pop('_tower_unread', None)                             # from TowerReader.apply (absent: no field)
    out, missing = [], 0
    for key in SLOTS:
        t = have.get(key)
        prev = last.get(key)
        if t is None:
            missing += 1
            t = dict(prev) if prev else dict(owner=key[0], kind=key[1], side=key[2], alive=True, hp_frac=1.0, score=0.0)
            t['carried'] = True
        elif prev is not None and not prev['alive'] and t.get('alive') and not t.get('revived'):
            t = dict(t, alive=False, hp_frac=0.0, hp_read=0)            # dead stays dead (unless the reader revived it)
        if unread is not None:
            t['unread'] = unread.get(f'{key[0]}/{key[1]}/{key[2]}', 0)
        last[key] = {k: v for k, v in t.items() if k != 'carried'}
        out.append(t)
    rec['towers'] = out
    return missing
