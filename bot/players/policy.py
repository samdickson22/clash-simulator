"""Policy players (no search): the v1 imitation policy and the R3a student.

Both wrap the frozen adapters used by X4S/S1 verbatim:
- v1: reports/explore/e1/policy.py V1Policy -> imitation/evaluation/standalone.py
  StandalonePlayer (stochastic T=1 gate->card->tile every 5 ticks).
- R3a: reports/explore/s1/cached_policy.py CachedPolicy(STUDENT, threshold) inside the
  same V1Policy wrapper, i.e. the K4S cutoff default played on its own: top-1 legal
  play when P(play) >= 0.50055 (calibrated to a 34.6% play rate), else WAIT.
"""
from __future__ import annotations

from .base import Decision, MatchContext, PublicView, WAIT

POLICY_SEED_OFFSET = 271828   # X4S plan.json policy.seed_offset


def make_poller(rt, ctx: MatchContext, source: str):
    """The per-seat 5-tick poller exactly as x4s/run.py:106-120 builds it."""
    from policy import V1Policy
    seed = ctx.seed + POLICY_SEED_OFFSET + ctx.seat
    if source == 'v1':
        return V1Policy(rt.POLICY, rt.R.builder, rt.R.costs, ctx.seat, list(ctx.own_order), seed), None
    from cached_policy import CachedPolicy
    if source == 'v1-cached':
        cached = CachedPolicy(rt.POLICY, None, None)
    elif source == 'R3a':
        cached = CachedPolicy(rt.STUDENT, rt.STUDENT.r3_threshold, None)
    else:
        raise ValueError(f'unknown policy source {source!r}')
    return V1Policy(cached, rt.R.builder, rt.R.costs, ctx.seat, list(ctx.own_order), seed), cached


class PolicyPlayer:
    deadline_seconds = None

    def __init__(self, rt, source='v1'):
        self.rt, self.source = rt, source
        self.name = {'v1': 'v1-policy', 'R3a': 'R3a-student', 'v1-cached': 'v1-cached'}[source]

    def start(self, ctx: MatchContext):
        self.ctx = ctx
        self.poller, self.cached = make_poller(self.rt, ctx, self.source)

    def act(self, view: PublicView) -> Decision:
        action = int(self.poller.poll(view.tick, view.reserved.packet, view.public_events))
        # 2305 (ability) is never submitted: abilities are disabled on both sides.
        return Decision(action if action < WAIT else WAIT)

    def close(self):
        pass
