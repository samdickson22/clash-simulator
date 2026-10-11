"""X4S S-default: S1's K-anytime kernel (anchor.py) with an R3a cutoff default.

EXPLORATION ONLY / NEVER ADOPTABLE. The scorer, admission rule and reduction are
byte-identical to reports/explore/s1/anchor.py. One rule is added after it:
if the deadline was hit and no legal play has a complete three-style score,
a student *play* replaces the frozen wait choice. A student WAIT keeps the frozen
choice (best complete wait, or the fallback if nothing completed). With no
deadline the result is identical to anchor.anytime, because hit is False.
coarse_order (student ranking) only reorders the coarse scan; refine_proposals
stays empty so no-deadline results equal the K4 reference.
"""
from anchor import planner_class as anchor_class, WAIT


def apply_default(core, action, default, candidates):
    stats = core.deadline_stats
    plays = [a for a in candidates if a < WAIT]
    scored = any(a < WAIT and s is not None
                 for a, s in zip(core.last['candidates'], core.last['scores']))
    use = bool(stats and stats['hit']) and bool(plays) and not scored and 0 <= default < WAIT
    if stats is not None:
        stats['student_default'] = use
        stats['frozen_action'] = int(action)
    if use:
        core.selected_wait_ticks = 0
        return int(default)
    return action


def planner_class(base):
    class Planner(anchor_class(base)):
        def score_candidates(self, root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
            action = super().score_candidates(root, seat, candidates, trace=trace,
                                              deadline=deadline, fallback=fallback)
            return apply_default(self, action, fallback, candidates)
    return Planner
