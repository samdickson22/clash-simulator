"""Fair public-information W-screen8 search player (K-anytime kernel, optional S-default).

Wraps, without changing them: fair_player.PublicPlanner (belief + public root),
s1/belief.Belief (deadline-resumable posterior), s1/anchor.py (K anytime W),
x4s/sdefault.py (R3a cutoff default) on the DelayAwarePlanner/C56RolloutPlanner
stack. The per-decision body is x4s/run.py:184-237.

Modes
- 'unbounded': no deadline. Frozen W-screen8 result (KU = K4 with no cutoff);
  deterministic. KU lost 19.33% vs v1 (k-anytime, 600 paired seeds).
- 'budget': deterministic anytime cutoff after `budget` complete 160-tick
  rollouts (virtual clock, one thread). Same scorer, same admission rule
  (only roots with all three styles complete count), same S-default rule.
- 'wall': the X4S arms: wall deadline `wall_ms` (incl. 8 ms reserve), `threads`
  scoring threads, honest lateness charged by the harness. Not reproducible.
"""
from __future__ import annotations

from .base import Decision, MatchContext, PublicView, SEARCH_INTERVAL, WAIT
from .policy import make_poller

RETURN_RESERVE = 0.008


def planner_class(kernel_base, sdefault_rule):
    """K4/K4S kernel plus a deterministic rollout-budget mode (virtual clock)."""
    import anchor

    class BudgetPlanner(kernel_base):
        rollout_budget = None   # None: delegate to the frozen deadline path

        def score_candidates(self, root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
            if self.rollout_budget is None:
                return super().score_candidates(root, seat, candidates, trace=trace,
                                                deadline=deadline, fallback=fallback)
            used = [0.]

            def clock():
                return used[0]

            def evaluate(action, style, horizon, remaining, private):
                # 1e6 s native budget = no wall check (the frozen no-deadline value).
                value = self.native.rollout_e1(private, seat, action, style, self.command_delay,
                    self.opponent_delay, horizon, self.config.interval, self.config.elixir_weight, 1e6)
                used[0] += horizon/self.config.horizon
                return value
            # anytime() discards a rollout that ends at/after the cutoff, so +0.5
            # admits exactly `rollout_budget` complete rollouts.
            action = anchor.anytime(self, root, seat, candidates, self.rollout_budget+.5, fallback,
                threads=1, coarse_horizon=self.coarse_horizon, clock=clock, evaluate=evaluate,
                coarse_order=self.coarse_order, refine_proposals=self.refine_proposals)
            if sdefault_rule is not None:
                action = sdefault_rule(self, action, fallback, candidates)
            self.deadline_stats['rollouts'] = used[0]
            return action
    return BudgetPlanner


class SearchPlayer:
    """W-screen8 search seat. default='R3a' -> K4S (S-default), 'v1' -> K4."""

    def __init__(self, rt, *, mode='budget', budget=48, wall_ms=200, threads=1,
                 default='R3a', coarse_horizon=160, reserve_floor=False, check_equivalence=0):
        if mode not in ('unbounded', 'budget', 'wall'):
            raise ValueError(mode)
        if mode != 'wall' and threads != 1:
            raise ValueError('deterministic modes use one scoring thread')
        self.rt, self.mode, self.budget, self.threads = rt, mode, budget, threads
        self.default, self.coarse_horizon, self.reserve_floor = default, coarse_horizon, reserve_floor
        self.deadline_seconds = wall_ms/1000 if mode == 'wall' else None
        kernel = 'K4S' if default == 'R3a' else 'K4'
        self.name = f'{kernel}-' + {'unbounded': 'unbounded', 'budget': f'b{budget}',
                                    'wall': f'{wall_ms}ms-t{threads}'}[mode]
        self.decisions = []
        # Debug: on the first k searched roots, also score with no budget and record
        # whether an uncut budget run reproduced the frozen unbounded choice.
        self.check_equivalence, self.equivalence = check_equivalence, []

    def start(self, ctx: MatchContext):
        rt, R = self.rt, self.rt.R
        from fair_player import PublicPlanner
        from delay import DelayAwarePlanner
        from clasher.rl.c56_rollout_planner import C56SearchConfig
        from belief import Belief
        if self.default == 'R3a':
            import sdefault
            base, rule = sdefault.planner_class(DelayAwarePlanner), sdefault.apply_default
        else:
            import anchor
            base, rule = anchor.planner_class(DelayAwarePlanner), None
        seed = ctx.seed + 100000   # x4s/run.py:103 search-seat seed
        from bot.fullpool.belief import planner_belief
        prior, belief_cls = planner_belief(rt, Belief)   # rt.PRIOR + Belief unless a full-pool prior is selected
        p = PublicPlanner(R, prior, seed)
        p.belief.__class__ = belief_cls
        p.core = planner_class(base, rule)(R.builder, R.bots, backend='native',
            seed=seed+1, native=R.native, native_config=R.config, catalog=rt.CAT,
            config=C56SearchConfig(threads=1, horizon=160, wait_screen8=False),
            command_delay=ctx.command_delay, delay_aware=True, symmetric_opponent=True,
            opponent_delay=ctx.opponent_delay, opponent_interval=10, opponent_capacity=1,
            max_outstanding=1, arm='W', variant='screen8', reserve_floor=self.reserve_floor,
            search_threads=self.threads, coarse_horizon=self.coarse_horizon)
        if self.mode == 'budget':
            p.core.rollout_budget = self.budget
        self.p = p
        # K4: unmodified v1 poller (fallback = v1 sample). K4S: cached R3a poller.
        self.poller, self.cached = make_poller(rt, ctx, 'v1' if self.default == 'v1' else 'R3a')

    def act(self, view: PublicView) -> Decision:
        import time
        p, R, info = self.p, self.rt.R, view.info
        wall0 = time.monotonic()
        fallback = int(self.poller.poll(view.tick, view.reserved.packet, view.public_events))
        fallback = fallback if fallback < WAIT else WAIT
        if not view.can_act:
            return Decision(WAIT, stats=None)
        if view.tick % SEARCH_INTERVAL:
            return Decision(WAIT, stats=None)
        cutoff = None if self.deadline_seconds is None else wall0+self.deadline_seconds-RETURN_RESERVE
        try:
            p.belief.update(info.tick, info.events, deadline=cutoff)
        except TimeoutError:
            p.core.selected_wait_ticks = 0
            return self._done(fallback, dict(hit=True, fallback=True, preparation_cutoff='belief'), wall0)
        p.core.info, p.core.costs, p.core.pending = info, R.costs, tuple(view.pending)
        p.core.opponent_elixir = self.poller.opponent_elixir
        if self.cached is not None:
            from imitation.evaluation.d1 import model_packet
            proposals = self.cached.propose(model_packet(view.reserved.packet, self.poller.mask),
                                            self.poller.player.last_d1)
            p.core.coarse_order = tuple(v['action'] for v in proposals)
        else:
            p.core.coarse_order = ()
        candidates, _ = p.core.candidates(view.reserved.packet, [])
        candidates = [a for a in candidates if a != 2305]
        if len(candidates) <= 1:
            p.core.selected_wait_ticks = 0
            return self._done(WAIT, dict(hit=False, fallback=False, candidates=len(candidates)), wall0)
        if cutoff is not None and time.monotonic() >= cutoff:
            p.core.selected_wait_ticks = 0
            return self._done(fallback, dict(hit=True, fallback=True, candidates=len(candidates)), wall0)
        try:
            opponent = p.belief.sample(p.rng, deadline=cutoff)
        except TimeoutError:
            p.core.selected_wait_ticks = 0
            return self._done(fallback, dict(hit=True, fallback=True, preparation_cutoff='sample'), wall0)
        root = R.root(info, opponent, p.rng)
        reference = None
        if self.mode == 'budget' and len(self.equivalence) < self.check_equivalence:
            p.core.rollout_budget = None
            try:
                reference = (int(p.core.score_candidates(root, view.seat, candidates, deadline=None,
                                                         fallback=fallback)), p.core.selected_wait_ticks)
            finally:
                p.core.rollout_budget = self.budget
        action = p.core.score_candidates(root, view.seat, candidates, deadline=cutoff, fallback=fallback)
        if reference is not None:
            hit = bool(p.core.deadline_stats['hit'])
            self.equivalence.append(dict(tick=view.tick, hit=hit, candidates=len(candidates),
                rollouts=p.core.deadline_stats.get('rollouts'), unbounded=reference[0], budget=int(action),
                equal=reference == (int(action), p.core.selected_wait_ticks)))
        stats = dict(p.core.deadline_stats or {})
        stats.setdefault('candidates', len(candidates))
        return self._done(int(action), stats, wall0, p.core.selected_wait_ticks)

    def _done(self, action, stats, wall0, wait_ticks=0):
        import time
        stats = dict(stats, action=int(action), wall_seconds=time.monotonic()-wall0)
        self.decisions.append(stats)
        return Decision(int(action) if action < WAIT else WAIT, int(wait_ticks), stats)

    def close(self):
        self.p.core.close()
