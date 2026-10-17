"""Separate HUD overlays (level badge, HP bar, deploy dial) from unit bodies in native-render frames.

The official client draws the level badge + HP bar only on damaged units and the deploy dial only during spawn, so
bodies must be cut out without them; overlays are cut out on their own (owner, offset to the body anchor) for the
compositor to re-add at its own rate.

- badge: the white "11" glyph + outline is identical for both teams; matched on a white-pixel mask, then the badge
  background hue gives the owner (blue = team 1 / own, red-pink = team 0 / enemy). Only hits that changed vs the empty
  background count (static tower crowns are ignored).
- hpbar: the changed, saturated run immediately right of a badge, within the badge's rows.
- deploy dial: a large gold ring (clock) during spawn; masked as its enclosing circle.
"""
from pathlib import Path

import cv2
import numpy as np

TEMPLATES = Path(__file__).resolve().parent / 'templates'


def _white(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return ((hsv[..., 1] < 60) & (hsv[..., 2] > 215)).astype(np.float32)


class Overlays:
    def __init__(self, threshold=0.62):
        badge = cv2.imread(str(TEMPLATES / 'badge_own_l11.png'), cv2.IMREAD_UNCHANGED)[..., :3]
        self.glyph = _white(badge)
        self.bh, self.bw = self.glyph.shape
        self.threshold = threshold

    def badges(self, img, changed):
        """-> [(x1, y1, x2, y2, owner, score)] for badges that are part of the frame change."""
        r = cv2.matchTemplate(_white(img), self.glyph, cv2.TM_CCOEFF_NORMED)
        hits = []
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        while True:
            _, score, _, (x, y) = cv2.minMaxLoc(r)
            if score < self.threshold:
                break
            r[max(0, y - self.bh // 2):y + self.bh // 2 + 1, max(0, x - self.bw // 2):x + self.bw // 2 + 1] = -1
            box = (x, y, x + self.bw, y + self.bh)
            if changed[box[1]:box[3], box[0]:box[2]].mean() < .3:
                continue  # static (tower crown badges, HUD)
            h = hsv[box[1]:box[3], box[0]:box[2]]
            sat = (h[..., 1] > 110) & (h[..., 2] > 120)
            blue = (sat & (h[..., 0] > 95) & (h[..., 0] < 125)).mean()
            red = (sat & ((h[..., 0] < 10) | (h[..., 0] > 160))).mean()
            if max(blue, red) < .2:
                continue
            hits.append((*box, 1 if blue > red else 0, float(score)))
        return hits

    @staticmethod
    def hpbars(img, changed, badges, damaged_px, max_len=120, min_rows=8):
        """Bars only next to badges of bodies the probe reports damaged (hp < maxHp). Measured own bar (15.535): dark
        blue outline (H~106 S255 V~97), grey-blue empty track (H111 S108 V113), light-cyan fill (H92 S102 V255),
        ~13 px tall, starting at the badge's right edge. A column belongs to the bar when >= min_rows of its changed
        pixels (within the badge's rows) are owner-hue family or grey track; the bar is the leading run of such columns."""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        bars = []
        for x1, y1, x2, y2, owner, _ in badges:
            if not any(abs(ax - (x1 + x2) / 2) < 90 and -20 < ay - y2 < 160 for ax, ay in damaged_px):
                continue
            h = hsv[y1:y2, x2:x2 + max_len]
            if h.size == 0:
                continue
            hue, sat, val = h[..., 0], h[..., 1], h[..., 2]
            family = ((hue >= 85) & (hue <= 120)) if owner == 1 else ((hue <= 12) | (hue >= 160))
            barlike = ((family & (sat > 80)) | ((sat < 140) & (val > 80) & (val < 150))) & changed[y1:y2, x2:x2 + max_len]
            col = barlike.sum(0) >= min_rows
            n = int(np.argmin(col)) if not col.all() else len(col)
            if n >= 10:
                rows = np.nonzero(barlike[:, :n].sum(1) >= n * .5)[0]
                top, bot = (y1 + int(rows.min()), y1 + int(rows.max()) + 1) if rows.size else (y1, y2)
                bars.append((x2, top, x2 + n, bot, owner))
        return bars

    @staticmethod
    def dials(img, changed, min_px=150):
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        gold = ((hsv[..., 0] > 15) & (hsv[..., 0] < 35) & (hsv[..., 1] > 110) & (hsv[..., 2] > 150)) & changed
        n, lab, st, _ = cv2.connectedComponentsWithStats(gold.astype(np.uint8), 8)
        out = []
        for i in range(1, n):
            if st[i][4] >= min_px and max(st[i][2], st[i][3]) >= 35:
                ys, xs = np.nonzero(lab == i)
                (cx, cy), rad = cv2.minEnclosingCircle(np.stack([xs, ys], 1).astype(np.float32))
                out.append((float(cx), float(cy), float(rad) + 3))
        return out

    def detect(self, img, changed, spawning, damaged_px=()):
        """-> (overlay_mask bool HxW, items [dict(type, box, owner)])."""
        h, w = changed.shape
        mask = np.zeros((h, w), bool)
        items = []
        bs = self.badges(img, changed)
        for x1, y1, x2, y2, owner, score in bs:
            mask[y1:y2, x1:x2] = True
            items.append(dict(type='badge', box=[x1, y1, x2, y2], owner=owner, score=round(score, 3)))
        for x1, y1, x2, y2, owner in self.hpbars(img, changed, bs, damaged_px):
            mask[y1:y2, x1:x2] |= changed[y1:y2, x1:x2]
            items.append(dict(type='hpbar', box=[x1, y1, x2, y2], owner=owner))
        if spawning:
            yy, xx = np.ogrid[:h, :w]
            for cx, cy, r in self.dials(img, changed):
                disk = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
                mask |= disk & changed
                items.append(dict(type='deploy_dial', box=[int(cx - r), int(cy - r), int(cx + r) + 1, int(cy + r) + 1],
                                  owner=None))
        return mask, items
