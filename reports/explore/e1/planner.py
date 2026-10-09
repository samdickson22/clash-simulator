"""Frozen W scoring when OFF; whole-root anytime reduction with a wall cutoff.

The clock and rollout evaluator are injectable. Partial/late roots never count.
The fallback is computed from the same public packet before search starts.
"""
import importlib.util
import math
from pathlib import Path
import time
from reserve import filter_candidates

WAIT = 2304
TIMED_WAITS = {2400: 10, 2401: 20, 2402: 40}
STYLES = ('balanced', 'pressure', 'defense')
spec = importlib.util.spec_from_file_location('e1_frozen_w_planner', Path(__file__).resolve().parents[1]/'w-screen8/planner.py')
frozen = importlib.util.module_from_spec(spec); spec.loader.exec_module(frozen)


def anytime(core, root, seat, candidates, deadline, fallback, *, clock=time.monotonic, evaluate=None):
    work = list(candidates)
    if not work or WAIT not in work:
        raise ValueError('E1 needs WAIT and legal candidates')
    scores = {}
    elixir = float(core.info.packet.observation.global_features[5])*10
    is_w = core.arm == 'W'
    def value(a, style):
        remaining = deadline-clock()
        if remaining <= 0:
            raise TimeoutError('E1 cutoff')
        result = (evaluate(a, style, remaining) if evaluate else
                  core.native.rollout_e1(root, seat, a, style, core.command_delay,
                      core.opponent_delay, core.config.horizon, core.config.interval,
                      core.config.elixir_weight, remaining))
        if clock() >= deadline:
            raise TimeoutError('E1 late rollout')
        return result
    hit = False
    try:
        if is_w:
            # Preserve frozen scan order, reduction order, and balanced-score reuse.
            first = {a: value(a, STYLES[0]) for a in work if a < WAIT}
            chosen = set(sorted(first, key=lambda a: (-first[a], work.index(a)))[:8])
            work = [a for a in work if a >= WAIT or a in chosen]
            for a in work:
                if a == 2400:
                    if WAIT in scores:
                        scores[a] = scores[WAIT]
                    continue
                score = first[a]/3 if a < WAIT else 0.
                for style in STYLES[1:] if a < WAIT else STYLES:
                    score += value(a, style)/3
                scores[a] = score
                # WAIT10 is exactly the same completed root, even if the next expires.
                if a == WAIT and 2400 in work:
                    scores[2400] = score
        else:
            # Root-major only when deadline is ON. Frozen style-major OFF is untouched.
            for a in work:
                score = 0.
                for style in STYLES:
                    score += value(a, style)/3
                scores[a] = score
    except TimeoutError:
        hit = True
    if is_w:
        for a in scores:
            ticks = TIMED_WAITS.get(a, 10 if a == WAIT else 0)
            if ticks and abs(scores[a]) < 2:
                scores[a] += .01*math.sqrt(ticks/20)*max(0., 1-elixir/10)
    best = None
    for a in work:
        if a in scores and (best is None or scores[a] > scores[best]+1e-9):
            best = a
    core.last = dict(candidates=work, scores=[scores.get(a) for a in work], traces=[])
    core.deadline_stats = dict(hit=hit, fallback=best is None, completed=len(scores), candidates=len(work))
    action = fallback if best is None else best
    core.selected_wait_ticks = TIMED_WAITS.get(action, 0)
    return action


def planner_class(base):
    class Planner(frozen.planner_class(base)):
        def __init__(self, *args, clock=time.monotonic, reserve_floor=False, **kw):
            super().__init__(*args, **kw)
            self.clock = clock
            if type(reserve_floor) is not bool:
                raise ValueError('reserve_floor must be boolean')
            self.reserve_floor = reserve_floor
            self.opponent_elixir = 0.
            self.floor_removed = 0
        def simulate_commands(self, root, seat, action, style, horizon, *, trace=False):
            if action in TIMED_WAITS:
                if trace:
                    raise ValueError('timed W traces are unavailable')
                value = self.native.rollout_e1(root, seat, action, style, self.command_delay,
                    self.opponent_delay, horizon, self.config.interval, self.config.elixir_weight, 1e6)
                return value, [], None
            return super().simulate_commands(root, seat, action, style, horizon, trace=trace)
        def candidates(self, packet, policy_proposals=()):
            actions, mask = super().candidates(packet, policy_proposals)
            filtered = filter_candidates(actions, packet, self.catalog, self.opponent_elixir, enabled=self.reserve_floor)
            self.floor_removed += len(actions)-len(filtered)
            return filtered, mask
        def score_candidates(self, root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
            if deadline is None:
                self.deadline_stats = None
                return super().score_candidates(root, seat, candidates, trace=trace)
            if trace:
                raise ValueError('E1 deadline mode has no traces')
            return anytime(self, root, seat, candidates, deadline, fallback, clock=self.clock)
    return Planner
