"""Students as Players: any R3-architecture checkpoint with a calibrated play threshold.

Spec strings (bot.eval.headline make_player):
- 'student:<path>'        threshold from '<path>.calibration.json' {"threshold": ...}
- 'student:<path>@<thr>'  explicit threshold
- 'student10:<path>[@thr]' same student, but it may only PLAY on 10-tick multiples (the teacher's search
  cadence, where every ExIt label is taken); it still polls every 5 ticks (D1 tracking).
The decode is R3a's exactly (s1/cached_policy.CachedPolicy with a threshold inside the
e1 V1Policy wrapper): top-1 legal play when P(play) >= threshold, else WAIT.
So 'student:R/R3a.pt@0.5005528330802917' reproduces PolicyPlayer(rt, 'R3a') bit for bit.
"""
from __future__ import annotations

import json
from pathlib import Path

from bot.players.base import Decision, MatchContext, PublicView, WAIT
from bot.players.policy import POLICY_SEED_OFFSET

_POLICIES: dict = {}


def parse_spec(spec: str):
    prefix, body = spec.split(':', 1)
    assert prefix in ('student', 'student10'), spec
    if '@' in body:
        path, thr = body.rsplit('@', 1)
        return Path(path), float(thr)
    path = Path(body)
    cal = Path(str(path) + '.calibration.json')
    return path, float(json.loads(cal.read_text())['threshold'])


def load_policy(path: Path, threshold: float):
    """Process-wide cache: one model per (path, threshold)."""
    key = (str(Path(path).resolve()), float(threshold))
    if key not in _POLICIES:
        from proposals import load_student
        _POLICIES[key] = load_student(path, threshold)
    return _POLICIES[key]


class StudentPlayer:
    deadline_seconds = None

    def __init__(self, rt, path, threshold, name=None, cadence=5):
        self.rt, self.path, self.threshold, self.cadence = rt, Path(path), float(threshold), int(cadence)
        self.name = name or f'student:{self.path.name}'

    @classmethod
    def from_spec(cls, rt, spec):
        path, thr = parse_spec(spec)
        return cls(rt, path, thr, name=spec, cadence=10 if spec.startswith('student10:') else 5)

    def start(self, ctx: MatchContext):
        from policy import V1Policy
        from cached_policy import CachedPolicy
        self.ctx = ctx
        policy = load_policy(self.path, self.threshold)
        self.cached = CachedPolicy(policy, self.threshold, None)
        seed = ctx.seed + POLICY_SEED_OFFSET + ctx.seat
        self.poller = V1Policy(self.cached, self.rt.R.builder, self.rt.R.costs, ctx.seat,
                               list(ctx.own_order), seed)

    def act(self, view: PublicView) -> Decision:
        action = int(self.poller.poll(view.tick, view.reserved.packet, view.public_events))
        if view.tick % self.cadence:
            return Decision(WAIT)
        return Decision(action if action < WAIT else WAIT)

    def close(self):
        pass
