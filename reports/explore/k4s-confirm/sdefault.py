"""PREREG-K4S S-default rule (r3 §2.3 item 3), ported from reports/explore/x4s2/sdefault.py (full rule only).

Reference bytes: x4s2/sdefault.py sha256 6da69e5d... The full rule is unchanged; the X4S2-only
"lite" variant is not ported (r3 §1.3: no S-lite).
If the scoring deadline was hit and no legal play has a complete three-style score, an SD1
*play* replaces the frozen choice (selected_wait_ticks = 0). An SD1 WAIT keeps the frozen choice.
Whenever any play has a complete score, the frozen best-complete-score rule stands.
With no deadline the rule equals anchor_x.anytime, because hit is False.
Preparation cutoffs (belief, pre-scan, sample) never reach this function; run.py returns the
seat poll, which for K4S is the SD1 default.
"""
from anchor_x import planner_class as anchor_class, WAIT


def apply_default(core, action, default, candidates):
    stats = core.deadline_stats
    plays = [a for a in candidates if a < WAIT]
    scored = any(a < WAIT and s is not None
                 for a, s in zip(core.last['candidates'], core.last['scores']))
    use = bool(stats and stats['hit']) and bool(plays) and not scored and 0 <= default < WAIT
    if stats is not None:
        stats['student_default'] = use
        stats['frozen_action'] = int(action)
        stats['default_rule'] = 'full'
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
