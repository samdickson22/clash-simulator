"""Per-match unit post-filter (perception round 2, exploration): fewer phantom units at equal recall.

Round-1 phantoms on validation (r2/diag_fp.py, thr .4): 44% displaced 1-2 tiles, 33% duplicate splits next to a real
detection, 16% isolated flicker. Phantom units cost win rate about as much as misses (reports/live/perception/ABLATION.md).

UnitFilter(hi, lo, nms, confirm) on each processed frame's units (record frame, any score >= lo):
  nms      same-owner, cross-identity suppression: a unit within `nms` tiles of a higher-scoring kept unit is dropped
           (duplicate splits); 0 = off.
  hi / lo  hysteresis: a unit continuing a unit kept in the previous frame (same owner and card, <= `link` tiles) needs only
           score >= lo; a new unit needs >= hi.
  confirm  a new unit is emitted only once it was also a candidate (>= lo, same owner and card, <= link) in the previous
           processed frame (one frame of latency, ~100 ms at 10 FPS); 0 = off.
reset() per match. Stateless thresholding = UnitFilter(hi=t, lo=t).
"""
import math


class UnitFilter:
    def __init__(self, hi=.5, lo=.5, nms=0., confirm=0, link=1.0):
        assert lo <= hi
        self.hi, self.lo, self.nms, self.confirm, self.link = hi, lo, nms, confirm, link
        self.reset()

    def reset(self):
        self.prev_kept, self.prev_cand = [], []

    def _near(self, u, pool):
        return any(p['owner'] == u['owner'] and p['card'] == u['card'] and math.hypot(p['x']-u['x'], p['y']-u['y']) <= self.link
                   for p in pool)

    def __call__(self, units):
        cand = sorted((u for u in units if u['score'] >= self.lo), key=lambda u: -u['score'])
        kept = []
        for u in cand:
            if self.nms and any(k['owner'] == u['owner'] and math.hypot(k['x']-u['x'], k['y']-u['y']) < self.nms for k in kept):
                continue
            if self._near(u, self.prev_kept):
                kept.append(u)
            elif u['score'] >= self.hi and (not self.confirm or self._near(u, self.prev_cand)):
                kept.append(u)
        self.prev_kept, self.prev_cand = kept, cand
        return kept
