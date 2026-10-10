"""S1 coarse-first W; K2 anchor remains byte-exact in anchor.py."""
import math,time
from anchor import e1,WAIT,TIMED_WAITS,STYLES

def anytime(core, root, seat, candidates, deadline, fallback, *, clock=time.monotonic, evaluate=None):
    work = list(candidates)
    if not work or WAIT not in work:
        raise ValueError('E1 needs WAIT and legal candidates')
    scores = {}
    elixir = float(core.info.packet.observation.global_features[5])*10
    is_w = core.arm == 'W'
    def value(a, style):
        remaining = 1e6 if deadline is None else deadline-clock()
        if remaining <= 0:
            raise TimeoutError('E1 cutoff')
        result = (evaluate(a, style, remaining) if evaluate else
                  core.native.rollout_e1(root, seat, a, style, core.command_delay,
                      core.opponent_delay, core.config.horizon, core.config.interval,
                      core.config.elixir_weight, remaining))
        if deadline is not None and clock() >= deadline:
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
    class Planner(e1.planner_class(base)):
        def __init__(self,*args,search_threads=1,coarse_horizon=160,**kw):
            assert search_threads==1 and coarse_horizon==160
            super().__init__(*args,**kw)
            self.search_threads=1; self.coarse_horizon=160
        def close(self): pass
        def score_candidates(self,root,seat,candidates,*,trace=False,deadline=None,fallback=WAIT):
            assert self.arm=="W" and not trace
            return anytime(self,root,seat,candidates,deadline,fallback,clock=self.clock)
    return Planner
