"""Live deadline adapter over the frozen Stage 5 public reconstruction.

The caller starts the clock before sensor conversion and supplies that absolute
perf_counter deadline. Without one, the budget starts at decide entry. Native
workers consume candidates in priority order; result reduction uses that same
order, regardless of worker completion order. Only fully evaluated candidates
count. Scheduling can affect which candidates finish, never their scores or the
tie-break among a fixed completed set. This is cooperative wall-clock admission,
not an operating-system realtime guarantee under arbitrary preemption.
"""
import time
from dataclasses import replace
from fair_player import PublicPlanner
from clasher.rl.c56_rollout_planner import C56SearchConfig


class DeadlinePublicPlanner(PublicPlanner):
    def __init__(self, resources, prior, seed, *, deadline_seconds=.2, threads=2):
        super().__init__(resources, prior, seed)
        self.core.config = C56SearchConfig(deadline_seconds=deadline_seconds, threads=threads)

    def decide(self, info, decision, *, deadline=None):
        if deadline is None and self.core.config.deadline_seconds is not None:
            deadline = time.perf_counter() + self.core.config.deadline_seconds
        self.core.deadline_stats = None
        self.belief.update(info.tick, info.events)
        candidates, mask = self.core.candidates(info.packet)
        if decision % 2 or len(candidates) == 1:
            return 2304, False
        if deadline is not None and time.perf_counter() >= deadline:
            self.core.deadline_stats = dict(completed=0, total=len(candidates), truncated=True, fallback=True)
            return candidates[0], True
        opponent = self.belief.sample(self.rng)
        root = self.resources.root(info, opponent, self.rng)
        action = self.core.score_candidates(root, info.seat, candidates, deadline=deadline)
        self.last = self.core.last
        return action, True
