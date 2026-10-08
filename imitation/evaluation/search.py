"""Arm B: unchanged Stage 5b search with matched candidate count and CPU D1."""
from dataclasses import replace
import time
import numpy as np
from .d1 import D1Tracker, model_packet
from deadline_player import DeadlinePublicPlanner


from .candidates import replacement_candidates
from .fast_prior import ExactFastPrior

class MatchedDeadlinePlayer(DeadlinePublicPlanner):
    """Stage 5b arm A with an exactly equivalent faster public-prior update."""
    def __init__(self, resources, prior, seed, *, deadline_seconds=.2, threads=2):
        super().__init__(resources, prior, seed, deadline_seconds=deadline_seconds, threads=threads)
        # Same layout/initial state; switch only the tested array operations.
        self.belief.__class__ = ExactFastPrior


class ImitationDeadlinePlayer(MatchedDeadlinePlayer):
    def __init__(self, resources, prior, seed, policy, seat, own_order):
        super().__init__(resources, prior, seed, deadline_seconds=.2, threads=2)
        self.policy = policy
        self.d1 = D1Tracker(resources.builder, resources.costs, seat, own_order)
        self.last_d1 = None
        self.proposal_ms = 0.
        self.candidate_counts = None

    def decide(self, info, decision, *, public_events, deadline=None):
        if deadline is None:
            deadline = time.perf_counter() + .2
        self.core.deadline_stats = None
        self.belief.update(info.tick, info.events)
        self.last_d1 = self.d1.update(info.tick, public_events)
        baseline, mask = self.core.candidates(info.packet)
        self.proposal_ms = 0.
        if decision % 2 or len(baseline) == 1:
            return 2304, False
        config = self.core.config
        try:
            self.core.config = replace(config, samples=0)
            base, _ = self.core.candidates(info.packet)
        finally:
            self.core.config = config
        start = time.perf_counter()
        proposals = ([] if start >= deadline else
                     self.policy.propose(model_packet(info.packet, mask), self.last_d1, k=8))
        self.proposal_ms = (time.perf_counter()-start)*1000
        candidates = replacement_candidates(base, baseline, [p['action'] for p in proposals], mask, self.core.rng)
        self.candidate_counts = (len(baseline), len(candidates))
        if time.perf_counter() >= deadline:
            self.core.deadline_stats = dict(completed=0, total=len(candidates), truncated=True, fallback=True)
            return candidates[0], True
        opponent = self.belief.sample(self.rng)
        root = self.resources.root(info, opponent, self.rng)
        action = self.core.score_candidates(root, info.seat, candidates, deadline=deadline)
        self.last = self.core.last
        return action, True
