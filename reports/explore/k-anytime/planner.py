"""WAIT-first W-screen8, complete roots only, bounded GIL-release threads.

X interface: coarse_order changes scheduling only; refine_proposals adds eligible
plays to the frozen top-eight refinement. Both hooks default empty for K.
"""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import importlib.util
import math
from pathlib import Path
import time

_spec = importlib.util.spec_from_file_location('k_e1_planner', Path(__file__).resolve().parents[1]/'e1/planner.py')
e1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e1)
WAIT, TIMED_WAITS, STYLES = e1.WAIT, e1.TIMED_WAITS, e1.STYLES


def anytime(core, root, seat, candidates, deadline, fallback, *, threads=1,
            coarse_horizon=160, clock=time.monotonic, evaluate=None,
            coarse_order=(), refine_proposals=(), pool=None):
    original = list(candidates)
    if WAIT not in original or len(set(original)) != len(original):
        raise ValueError('unique candidates including WAIT required')
    cutoff = float('inf') if deadline is None else deadline
    plays = [a for a in original if a < WAIT]
    hinted = list(dict.fromkeys(a for a in coarse_order if a in plays))
    scan = hinted + [a for a in plays if a not in hinted]
    full_horizon = core.config.horizon
    scores, first = {}, {}
    hit = False
    owned_pool = threads > 1 and pool is None
    executor = ThreadPoolExecutor(max_workers=threads) if owned_pool else pool

    def job(action, styles, horizon, prior):
        # Clone before releasing the GIL: no concurrent mutable native root borrow.
        private = root.clone() if threads > 1 and evaluate is None else root
        score = prior
        for style in styles:
            remaining = cutoff - clock()
            if remaining <= 0:
                raise TimeoutError('K cutoff')
            value = (evaluate(action, style, horizon, remaining, private) if evaluate else
                     core.native.rollout_e1(private, seat, action, style,
                         core.command_delay, core.opponent_delay, horizon,
                         core.config.interval, core.config.elixir_weight,
                         1e6 if deadline is None else remaining))
            if clock() >= cutoff:
                raise TimeoutError('K late rollout')
            score += value / (1 if styles == (STYLES[0],) else 3)
        return score

    def phase(tasks, target):
        nonlocal hit
        if threads == 1:
            for action, styles, horizon, prior in tasks:
                try:
                    target[action] = job(action, styles, horizon, prior)
                except TimeoutError:
                    hit = True
                    return False
            return True
        iterator = iter(tasks)
        active = {}
        stopped = False
        def fill():
            nonlocal stopped, hit
            while len(active) < threads and not stopped:
                try:
                    args = next(iterator)
                except StopIteration:
                    stopped = True
                    break
                if clock() >= cutoff:
                    hit, stopped = True, True
                    break
                active[executor.submit(job, *args)] = args[0]
        fill()
        while active:
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                action = active.pop(future)
                try:
                    # Job checked the final clock before completing. Collection
                    # time is irrelevant; a completed pre-cutoff score is eligible.
                    target[action] = future.result()
                except TimeoutError:
                    hit, stopped = True, True
            fill()
        return not hit

    try:
        # Original WAIT completes before any timed wait starts, including K4.
        ok = phase([(WAIT, STYLES, full_horizon, 0.)], scores)
        if WAIT in scores and 2400 in original:
            scores[2400] = scores[WAIT]
        if ok:
            ok = phase([(a, STYLES, full_horizon, 0.) for a in original
                        if a >= WAIT and a not in (WAIT, 2400)], scores)
        if ok:
            ok = phase([(a, (STYLES[0],), coarse_horizon, 0.) for a in scan], first)
        if ok:
            chosen = set(sorted(plays, key=lambda a: (-first[a], original.index(a)))[:8])
            chosen.update(a for a in refine_proposals if a in plays)
            work = [a for a in original if a >= WAIT or a in chosen]
            tasks = [(a, STYLES[1:] if coarse_horizon == full_horizon else STYLES,
                      full_horizon, first[a]/3 if coarse_horizon == full_horizon else 0.)
                     for a in work if a < WAIT]
            phase(tasks, scores)
        else:
            work = original
    finally:
        if owned_pool:
            executor.shutdown(wait=True, cancel_futures=True)
    elixir = float(core.info.packet.observation.global_features[5])*10
    for action in scores:
        ticks = TIMED_WAITS.get(action, 10 if action == WAIT else 0)
        if ticks and abs(scores[action]) < 2:
            scores[action] += .01*math.sqrt(ticks/20)*max(0., 1-elixir/10)
    best = None
    for action in work:
        if action in scores and (best is None or scores[action] > scores[best]+1e-9):
            best = action
    core.last = dict(candidates=work, scores=[scores.get(a) for a in work], traces=[])
    core.deadline_stats = dict(hit=hit, fallback=best is None, completed=len(scores), candidates=len(work))
    action = fallback if best is None else best
    core.selected_wait_ticks = TIMED_WAITS.get(action, 0)
    return action


def planner_class(base):
    class Planner(e1.planner_class(base)):
        def __init__(self, *args, search_threads=1, coarse_horizon=160, **kw):
            super().__init__(*args, **kw)
            if search_threads not in (1,4):
                raise ValueError('K supports one or four scoring threads')
            self.search_threads, self.coarse_horizon = search_threads, coarse_horizon
            self.coarse_order, self.refine_proposals = (), ()
            self._pool = None
        def close(self):
            if self._pool is not None:
                self._pool.shutdown(wait=True, cancel_futures=True)
                self._pool = None
        def score_candidates(self, root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
            if self.arm != 'W':
                return super().score_candidates(root, seat, candidates, trace=trace,
                                                deadline=deadline, fallback=fallback)
            if trace:
                raise ValueError('K has no traced scoring mode')
            if self.search_threads > 1 and self._pool is None:
                self._pool = ThreadPoolExecutor(max_workers=self.search_threads)
            return anytime(self, root, seat, candidates, deadline, fallback,
                threads=self.search_threads, coarse_horizon=self.coarse_horizon,
                clock=self.clock, coarse_order=self.coarse_order,
                refine_proposals=self.refine_proposals, pool=self._pool)
    return Planner
