"""Location-level play-event tracker over TemporalHead outputs (replaces per-card-channel EventFusion).

Per frame and side: existence = max over cards of sigmoid(event heatmap); 3x3 peaks >= `low`.
Peaks associate with live tracks of the same side within 1.5 tiles and 400 ms execution time;
tracks accumulate card probability mass and keep their max existence. A track is emitted once, with card =
argmax of accumulated mass. Placement: tile centre = (col/2, row/2), native coordinates. A second emission of the
same side+card within `repeat_ms` and `repeat_tiles` of an earlier one is suppressed (card cycling makes real
repeats that fast essentially impossible; this removed most duplicate spell emissions on validation).

Body fusion (`hold_ms` > 0; LIVE integration step, 2026-10-15). The event head often has the right place and time
but the wrong card (85/140 troop false positives on 16 val matches). The unit detections of the same frames carry
the newborn unit's identity (body head, units F1 0.84), so a track that crosses `threshold` is HELD until
`exec + hold_ms` (or `max_hold_ms` after the crossing, whichever is later is capped by it) and then emitted once with
the fused card. Card votes: unit detections (record frame, owner 0 = us; converted to native here) of the track's
side within `unit_radius` tiles of the event, in frames from `exec - vote_lead_ms` on, whose card was NOT seen
within `unit_radius` of the event in [exec - pre_ms, exec - vote_lead_ms] (newborn only; a pre-existing unit of
that card walking past is no evidence). Vote(c) = sum over frames of the best detection score of c (a swarm counts
once per frame) / processed frames since exec. If the
best newborn card b has vote >= `vote_min` and the event head's share p(b) >= `prior_min`, the event's card is b,
else the event head's argmax. An event whose head and bodies agree emits early (`agree_frames` agreeing frames); with `early_share`, a body-less
spell (BODYLESS) whose head share is >= early_share emits at the crossing.
The hold never re-emits: downstream (bot/live/translate.py) gets each event once with its final card, so the
frozen D1/OwnCycle mirrors and the belief, which cannot retract a play, stay consistent. Cost: emission latency
(measured in reports/live/integration/RESULTS.md). hold_ms=0 is the original tracker exactly.
"""
import math

import torch
from torch.nn import functional as F

OWN_NATIVE = 1  # native owner of the recorded viewpoint (common.OWN_NATIVE)
# Spells that leave no unit body to vote with (GoblinBarrel, RoyalDelivery and BarbLog spawn units, so they wait).
BODYLESS = frozenset({'Arrows', 'Earthquake', 'Fireball', 'Lightning', 'Log', 'Poison', 'Rocket', 'Tornado', 'Zap'})


# Live default (LIVE integration (b), 2026-10-15): chosen over the even-half pick (thr .5, hold 700) because both tie on
# bot-level agreement (it5s2 .856 vs .857, K4CW tied) while this one lets 44% fewer wrong plays reach the bot (58 vs 104
# on 64 val matches; a fake play corrupts the opponent elixir/cycle tracking) for -3 pp plays reached (.775 vs .807).
LIVE_DEFAULT = dict(threshold=.6, hold_ms=500., max_hold_ms=500., vote_min=.35, prior_min=.02, unit_radius=1.5,
                    agree_frames=2, early_share=.6)


class EventTracker:
    def __init__(self, cards, threshold=.6, low=.2, radius=1.5, dt_ms=400., expire_ms=700., repeat_ms=3000., repeat_tiles=4.,
                 hold_ms=0., max_hold_ms=900., unit_radius=2.0, vote_lead_ms=150., pre_ms=1500., vote_min=.5, prior_min=.0,
                 agree_frames=2, unit_floor=.25, early_share=None, early_cards=BODYLESS):
        self.cards = list(cards); self.n = len(cards); self.th = threshold; self.low = low
        self.radius = radius; self.dt = dt_ms; self.expire = expire_ms; self.tracks = []
        self.repeat_ms, self.repeat_tiles = repeat_ms, repeat_tiles; self.history = []
        self.hold, self.max_hold, self.ur = hold_ms, max_hold_ms, unit_radius
        self.lead, self.pre, self.vote_min, self.prior_min, self.agree = vote_lead_ms, pre_ms, vote_min, prior_min, agree_frames
        self.unit_floor = unit_floor
        self.early_share, self.early = early_share, {i for i, c in enumerate(self.cards) if c in early_cards}
        self.idx = {c: i for i, c in enumerate(self.cards)}
        self.frames = []      # (now_ms, [(native side, card idx, x, y, score)]) for the last pre_ms + max hold
        self.revised = 0

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

    # -- body fusion ---------------------------------------------------------------------------
    def _add_units(self, now_ms, units):
        rows = []
        for u in units or ():
            c = self.idx.get(u.get('card'))
            if c is None or u.get('score', 1.) < self.unit_floor:
                continue
            side = OWN_NATIVE if int(u['owner']) == 0 else 1-OWN_NATIVE
            rows.append((side, c, float(u['x']), 32.-float(u['y']), float(u.get('score', 1.))))
        self.frames.append((now_ms, rows))
        keep = self.pre+self.max_hold+self.dt+1000.
        while self.frames and now_ms-self.frames[0][0] > keep:
            self.frames.pop(0)

    def votes(self, t):
        """-> (votes tensor[n] = summed newborn detection score / frames since exec, frames since exec)."""
        v = torch.zeros(self.n); pre = set(); nf = 0
        lo = t['exec']-self.lead
        for ts, rows in self.frames:
            if ts < t['exec']-self.pre:
                continue
            near = [(c, s) for side, c, x, y, s in rows if side == t['side'] and math.hypot(x-t['x'], y-t['y']) <= self.ur]
            if ts < lo:
                pre.update(c for c, _ in near)
                continue
            nf += ts >= t['exec']
            best = {}
            for c, s in near:          # per frame: max score per card (a swarm counts once, like a single unit)
                if c not in pre and s > best.get(c, 0.):
                    best[c] = s
            for c, s in best.items():
                v[c] += s
        return v/max(1, nf), nf

    def fused(self, t):
        mass = t['mass']; head = int(mass.argmax())
        if self.hold <= 0:
            return head, 0
        v, nf = self.votes(t)
        b = int(v.argmax()); share = float(mass[b]/mass.sum().clamp(min=1e-9))
        if v[b] >= self.vote_min and share >= self.prior_min:
            return b, int(round(float(v[head])*nf))
        return head, int(round(float(v[head])*nf))

    def _emit(self, t, now_ms, emitted):
        t['emitted'] = True
        c, _ = self.fused(t)
        if c != int(t['mass'].argmax()):
            self.revised += 1
        card = self.cards[c]
        s = t['side']
        self.history = [h for h in self.history if now_ms-h[0] <= self.repeat_ms]
        if any(h[1] == s and h[2] == card and math.hypot(h[3]-t['x'], h[4]-t['y']) <= self.repeat_tiles for h in self.history):
            return
        self.history.append((now_ms, s, card, t['x'], t['y']))
        emitted.append(dict(side=s, card=card, x_tiles=t['x'], y_tiles=t['y'], execution_timestamp_ms=t['exec'],
                            existence_q=t['score'], det_ms=now_ms, head_card=self.cards[int(t['mass'].argmax())]))

    def update(self, out, now_ms, peaks=None, units=None):
        """units: this frame's unit detections in the record frame ({card, owner, x, y, score}; owner 0 = us),
        used only when hold_ms > 0."""
        peaks = self.peaks(out) if peaks is None else peaks
        if self.hold > 0:
            self._add_units(now_ms, units)
        self.tracks = [t for t in self.tracks if now_ms-t['last'] <= self.expire or (t['crossed'] is not None and not t['emitted'])]
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
                best = dict(side=s, x=x, y=y, exec=exec_ms, score=0., mass=torch.zeros(self.n), last=now_ms, emitted=False, w=0.,
                            crossed=None)
                self.tracks.append(best)
            if best['emitted'] and self.hold > 0:
                continue      # a held track is final once emitted; later peaks only keep it alive (no re-emission)
            if e > best['score']:
                best['x'], best['y'] = x, y
            best['score'] = max(best['score'], e); best['mass'] += probs*e; best['last'] = now_ms
            best['exec'] = (best['exec']*best['w']+exec_ms*e)/(best['w']+e); best['w'] += e
            if not best['emitted'] and best['score'] >= self.th:
                if self.hold <= 0:
                    self._emit(best, now_ms, emitted)
                elif best['crossed'] is None:
                    best['crossed'] = now_ms
        if self.hold > 0:
            for t in self.tracks:
                if t['emitted'] or t['crossed'] is None:
                    continue
                due = now_ms >= min(t['exec']+self.hold, t['crossed']+self.max_hold)
                if not due and self.early_share is not None:     # a confident body-less spell has nothing to wait for
                    head = int(t['mass'].argmax())
                    due = head in self.early and float(t['mass'][head]/t['mass'].sum().clamp(min=1e-9)) >= self.early_share
                if not due and self.agree:
                    head = int(t['mass'].argmax()); v, nf = self.votes(t)
                    due = int(v.argmax()) == head and float(v[head])*nf >= self.agree*.5 and v[head] >= self.vote_min
                if due:
                    self._emit(t, now_ms, emitted)
        return emitted
