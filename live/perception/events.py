"""Location-level play-event tracker over TemporalHead outputs (replaces per-card-channel EventFusion).

Per frame and side: existence = max over cards of sigmoid(event heatmap); 3x3 peaks >= `low`.
Peaks associate with live tracks of the same side within 1.5 tiles and 400 ms execution time;
tracks accumulate card probability mass and keep their max existence. A track is emitted once,
the first frame its max existence >= `threshold`, with card = argmax of accumulated mass.
Placement: tile centre = (col/2, row/2), native coordinates. A second emission of the same side+card
within `repeat_ms` and `repeat_tiles` of an earlier one is suppressed (card cycling makes real repeats
that fast essentially impossible; this removed most duplicate spell emissions on validation).
"""
import math

import torch
from torch.nn import functional as F


class EventTracker:
    def __init__(self, cards, threshold=.6, low=.2, radius=1.5, dt_ms=400., expire_ms=700., repeat_ms=3000., repeat_tiles=4.):
        self.cards = list(cards); self.n = len(cards); self.th = threshold; self.low = low
        self.radius = radius; self.dt = dt_ms; self.expire = expire_ms; self.tracks = []
        self.repeat_ms, self.repeat_tiles = repeat_ms, repeat_tiles; self.history = []

    def peaks(self, out):
        """-> list of (side, x, y, existence, card_probs[n] tensor(cpu), exec_offset_age_ms)."""
        sc = out['event_heatmap'][0].float().sigmoid().view(2, self.n, 64, 36)
        ex, arg = sc.max(1)  # [2,64,36]
        pk = (ex == F.max_pool2d(ex[None], 3, 1, 1)[0]) & (ex >= self.low)
        res = []
        age = out['event_age_ms'][0].float().view(2, self.n, 64, 36)
        for s, y, x in torch.nonzero(pk).tolist():
            probs = sc[s, :, y, x]; c = int(arg[s, y, x])
            res.append((s, x/2., y/2., float(ex[s, y, x]), probs.cpu(), float(age[s, c, y, x])))
        return res

    def update(self, out, now_ms, peaks=None):
        peaks = self.peaks(out) if peaks is None else peaks
        self.tracks = [t for t in self.tracks if now_ms-t['last'] <= self.expire]
        emitted = []
        for s, x, y, e, probs, age in sorted(peaks, key=lambda p: -p[3]):
            exec_ms = now_ms-age; best = None; bd = 1e9
            for t in self.tracks:
                if t['side'] != s or abs(t['exec']-exec_ms) > self.dt:
                    continue
                d = math.hypot(t['x']-x, t['y']-y)
                if d <= self.radius and d < bd:
                    best, bd = t, d
            if best is None:
                best = dict(side=s, x=x, y=y, exec=exec_ms, score=0., mass=torch.zeros(self.n), last=now_ms, emitted=False, w=0.)
                self.tracks.append(best)
            if e > best['score']:
                best['x'], best['y'] = x, y
            best['score'] = max(best['score'], e); best['mass'] += probs*e; best['last'] = now_ms
            best['exec'] = (best['exec']*best['w']+exec_ms*e)/(best['w']+e); best['w'] += e
            if not best['emitted'] and best['score'] >= self.th:
                best['emitted'] = True
                card = self.cards[int(best['mass'].argmax())]
                self.history = [h for h in self.history if now_ms-h[0] <= self.repeat_ms]
                if any(h[1] == s and h[2] == card and math.hypot(h[3]-best['x'], h[4]-best['y']) <= self.repeat_tiles for h in self.history):
                    continue
                self.history.append((now_ms, s, card, best['x'], best['y']))
                emitted.append(dict(side=s, card=card, x_tiles=best['x'], y_tiles=best['y'],
                                    execution_timestamp_ms=best['exec'], existence_q=best['score'], det_ms=now_ms))
        return emitted
