"""Search-compute variants of the K4S W-screen8 search player (exploration).

Every variant keeps the frozen scorer: `s1/anchor.anytime` (WAIT -> timed waits ->
coarse balanced scan of every play -> top-8 refine with pressure/defense) and the
x4s S-default rule, on the same PublicPlanner/DelayAwarePlanner stack as
bot/players/search.py. Nothing frozen is edited; compute is added along one axis:

- m<M>   M determinizations. Root 0 is drawn from the planner rng exactly as K4S
         does (so m1 == K4S); roots 1..M-1 come from a separate generator keyed by
         (search seed, tick). Every rollout the scorer asks for is run on all M roots
         and the frozen scorer sees the MEAN, so screening, top-8 selection and the
         final argmax all use the mean over determinizations (PIMC averaging).
- w<N>   N random legal samples in the candidate set instead of 16.
- st     the R3a student's top-8 legal plays (its ranking, ignoring its play/wait gate) are
         passed as policy_proposals, i.e. inserted into the candidate list after the scripted
         plays and before the random samples (K4S only uses them to order the coarse scan).
         They are then scored like every other play (coarse scan, top-8 refine). Because the
         frozen top-8 and argmax break exact ties by list position, st also wins ties for them.
- stl    as st, but the student plays are appended at the END of the list (they lose ties).
- sr     as st, and the student plays are also forced into the 3-style refinement
         (anytime's refine_proposals hook).
- h<T>   rollout horizon T ticks (coarse and refine) instead of 160.
- b<N>   optional per-decision cut after N single-root rollouts (virtual clock);
         default: no cut. K4S-b64 never cuts (a full decision is <= 46 rollouts).

Names: 'K4S-' + '-'.join(tokens), e.g. K4S-m4, K4S-w48, K4S-st, K4S-h320, K4S-st-w48.
Deterministic: no wall clock enters any decision.
"""
from __future__ import annotations

import math
import re

import numpy as np

from bot.players.base import Decision, MatchContext, PublicView, SEARCH_INTERVAL, WAIT
from bot.players.policy import make_poller
from bot.players.search import SearchPlayer

EXTRA_ROOT_KEY = 0x5ea4c4   # separates the extra-root generator from every frozen stream
STYLES = ('balanced', 'pressure', 'defense')
TIMED_WAITS = {2400: 10, 2401: 20, 2402: 40}


def planner_class(kernel_base, sdefault_rule):
    import anchor

    class MultiRootPlanner(kernel_base):
        rollout_budget = None   # single-root rollouts per decision; None = no cut
        roots = ()

        def score_candidates(self, root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
            roots = list(self.roots) or [root]
            assert roots[0] is root
            used, values = [0.], {}

            def clock():
                return used[0]

            def evaluate(action, style, horizon, remaining, private):
                vals = []
                for r in roots:
                    # 1e6 s native budget = no wall check (the frozen no-deadline value).
                    vals.append(self.native.rollout_e1(r, seat, action, style, self.command_delay,
                        self.opponent_delay, horizon, self.config.interval, self.config.elixir_weight, 1e6))
                    used[0] += horizon/self.config.horizon
                values[action, style] = vals
                # sum([x])/1 == x exactly, so one root reproduces K4S bit for bit.
                return sum(vals)/len(vals)
            cutoff = None if self.rollout_budget is None else self.rollout_budget+.5
            action = anchor.anytime(self, root, seat, candidates, cutoff, fallback,
                threads=1, coarse_horizon=self.coarse_horizon, clock=clock, evaluate=evaluate,
                coarse_order=self.coarse_order, refine_proposals=self.refine_proposals)
            if sdefault_rule is not None:
                action = sdefault_rule(self, action, fallback, candidates)
            self.deadline_stats['rollouts'] = used[0]
            if len(roots) > 1:
                self.deadline_stats.update(self._diagnostics(values, len(roots), int(action)))
            return action

        def _diagnostics(self, values, m, chosen):
            """Which action a single root / the worst root would have picked from the same work set."""
            elixir = float(self.info.packet.observation.global_features[5])*10
            per_root = {}
            for a in self.last['candidates']:
                key = WAIT if a == 2400 else a
                if not all((key, s) in values for s in STYLES):
                    continue
                bonus = 0.
                ticks = TIMED_WAITS.get(a, 10 if a == WAIT else 0)
                rows = [sum(values[key, s][k] for s in STYLES)/3 for k in range(m)]
                if ticks:
                    bonus = .01*math.sqrt(ticks/20)*max(0., 1-elixir/10)
                per_root[a] = [x+bonus if abs(x) < 2 else x for x in rows]
            if not per_root:
                return {}
            order = list(per_root)
            pick = lambda f: max(order, key=lambda a: (f(per_root[a]), -order.index(a)))
            root0 = [pick(lambda r, k=k: r[k]) for k in range(m)]
            spread = per_root.get(chosen)
            return dict(roots=m,
                        root_disagree=sum(a != chosen for a in root0)/m,
                        min_disagree=pick(min) != chosen,
                        chosen_sd=float(np.std(spread)) if spread else None)
    return MultiRootPlanner


class MultiSearchPlayer(SearchPlayer):
    """K4S with more search compute along one or more axes (see module docstring)."""

    def __init__(self, rt, *, roots=1, samples=16, student_candidates=False, horizon=160,
                 budget=None, student_last=False, student_refine=False, name=None):
        super().__init__(rt, mode='unbounded', default='R3a', coarse_horizon=horizon)
        if roots < 1 or samples < 0 or horizon <= 0:
            raise ValueError('invalid search variant')
        self.roots, self.samples, self.student_candidates = roots, samples, student_candidates
        self.horizon, self.budget = horizon, budget
        self.student_last, self.student_refine = student_last, student_refine
        self.name = name or 'K4S-variant'

    def start(self, ctx: MatchContext):
        rt, R = self.rt, self.rt.R
        from fair_player import PublicPlanner
        from delay import DelayAwarePlanner
        from clasher.rl.c56_rollout_planner import C56SearchConfig
        from belief import Belief
        import sdefault
        seed = ctx.seed + 100000   # x4s/run.py:103 search-seat seed (as SearchPlayer)
        p = PublicPlanner(R, rt.PRIOR, seed)
        p.belief.__class__ = Belief
        p.core = planner_class(sdefault.planner_class(DelayAwarePlanner), sdefault.apply_default)(
            R.builder, R.bots, backend='native', seed=seed+1, native=R.native, native_config=R.config,
            catalog=rt.CAT,
            config=C56SearchConfig(samples=self.samples, threads=1, horizon=self.horizon, wait_screen8=False),
            command_delay=ctx.command_delay, delay_aware=True, symmetric_opponent=True,
            opponent_delay=ctx.opponent_delay, opponent_interval=10, opponent_capacity=1,
            max_outstanding=1, arm='W', variant='screen8', reserve_floor=False,
            search_threads=1, coarse_horizon=self.horizon)
        p.core.rollout_budget = self.budget
        self.p, self.seed = p, seed
        self.poller, self.cached = make_poller(rt, ctx, 'R3a')

    def act(self, view: PublicView) -> Decision:
        # SearchPlayer.act (x4s/run.py:184-237 body) with no deadline, plus the variant hooks.
        import time
        p, R, info = self.p, self.rt.R, view.info
        wall0 = time.monotonic()
        fallback = int(self.poller.poll(view.tick, view.reserved.packet, view.public_events))
        fallback = fallback if fallback < WAIT else WAIT
        if not view.can_act or view.tick % SEARCH_INTERVAL:
            return Decision(WAIT, stats=None)
        p.belief.update(info.tick, info.events)
        p.core.info, p.core.costs, p.core.pending = info, R.costs, tuple(view.pending)
        p.core.opponent_elixir = self.poller.opponent_elixir
        from imitation.evaluation.d1 import model_packet
        proposals = self.cached.propose(model_packet(view.reserved.packet, self.poller.mask),
                                        self.poller.player.last_d1)
        p.core.coarse_order = tuple(v['action'] for v in proposals)
        student = [v['action'] for v in proposals]
        extra = student if self.student_candidates and not self.student_last else []
        candidates, mask = p.core.candidates(view.reserved.packet, extra)
        if self.student_last:
            candidates += [a for a in dict.fromkeys(student) if a not in candidates and a < WAIT and mask[a]]
        candidates = [a for a in candidates if a != 2305]
        p.core.refine_proposals = tuple(student) if self.student_refine else ()
        if len(candidates) <= 1:
            p.core.selected_wait_ticks = 0
            return self._done(WAIT, dict(hit=False, fallback=False, candidates=len(candidates)), wall0)
        opponent = p.belief.sample(p.rng)
        root = R.root(info, opponent, p.rng)
        roots = [root]
        if self.roots > 1:
            rng = np.random.default_rng([self.seed, EXTRA_ROOT_KEY, view.tick])
            for _ in range(self.roots-1):
                roots.append(R.root(info, p.belief.sample(rng), rng))
        p.core.roots = roots
        try:
            action = p.core.score_candidates(root, view.seat, candidates, deadline=None, fallback=fallback)
        finally:
            p.core.roots = ()
        stats = dict(p.core.deadline_stats or {})
        stats.setdefault('candidates', len(candidates))
        stats['resolved'] = p.belief.derived()['hand'] is not None and p.belief.derived()['cycle'] is not None
        return self._done(int(action), stats, wall0, p.core.selected_wait_ticks)


def make_search_player(rt, name):
    """'K4S-' + tokens: m<M>, w<N>, st, h<T>, b<N> (see module docstring)."""
    kw = dict(name=name)
    for token in name.split('-')[1:]:
        m = re.fullmatch(r'([mwhb])(\d+)', token)
        if m:
            kw[dict(m='roots', w='samples', h='horizon', b='budget')[m[1]]] = int(m[2])
        elif token in ('st', 'stl', 'sr'):
            kw.update(student_candidates=True, student_last=token == 'stl', student_refine=token == 'sr')
        else:
            raise ValueError(f'unknown search variant token {token!r} in {name!r}')
    return MultiSearchPlayer(rt, **kw)
