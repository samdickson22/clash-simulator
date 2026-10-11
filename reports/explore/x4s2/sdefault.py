"""X4S2 S-default rules on the anchor_x kernel (EXPLORATION ONLY / NEVER ADOPTABLE).

Copied from reports/explore/x4s/sdefault.py; the full rule ("S-default") is unchanged:
if the deadline was hit and no legal play has a complete three-style score, a student
*play* replaces the frozen wait choice. A student WAIT keeps the frozen choice.

The lite rule ("S-lite", X4S2 priority 3) additionally requires that the coarse scan
was incomplete: when every play finished its coarse rollout but no refined play
completed, the frozen choice (best complete wait) is kept. No other rule changes.
With no deadline both rules equal anchor_x.anytime, because hit is False.
"""
from anchor_x import planner_class as anchor_class, WAIT


def apply_default(core, action, default, candidates, lite=False):
    stats = core.deadline_stats
    plays = [a for a in candidates if a < WAIT]
    scored = any(a < WAIT and s is not None
                 for a, s in zip(core.last['candidates'], core.last['scores']))
    use = bool(stats and stats['hit']) and bool(plays) and not scored and 0 <= default < WAIT
    if lite and stats is not None:
        use = use and not stats['coarse_complete']
    if stats is not None:
        stats['student_default'] = use
        stats['frozen_action'] = int(action)
        stats['default_rule'] = 'lite' if lite else 'full'
    if use:
        core.selected_wait_ticks = 0
        return int(default)
    return action


def planner_class(base, lite=False):
    class Planner(anchor_class(base)):
        def score_candidates(self, root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
            action = super().score_candidates(root, seat, candidates, trace=trace,
                                              deadline=deadline, fallback=fallback)
            return apply_default(self, action, fallback, candidates, lite=lite)
    return Planner


def lite_planner_class(base):
    return planner_class(base, lite=True)
