"""LivePlayer: the best bot (K4C-r16) under a wall deadline, with an it5s2 fast tier (LIVE track, exploration).

Nothing frozen is edited. Two pieces:

- WallCandidatePlayer = bot/search/candidates.py CandidateSearchPlayer (K4C-r<N>) whose search takes a wall
  deadline and scoring threads, exactly as bot/players/search.py SearchPlayer does in mode='wall':
    cutoff = decision start + wall_ms - RETURN_RESERVE (8 ms); belief.update / belief.sample take the cutoff;
    the frozen K kernel (s1/anchor.anytime via x4s/sdefault) scores with `search_threads` threads, keeps only
    complete three-style roots, and at the cutoff applies the S-default rule with `fallback` as the default.
  MultiSearchPlayer hardcodes deadline=None, threads=1 (players.py ~52-78, 134-138, 178); this class only
  replaces start/act. With wall_ms=None it IS K4C-r<N> (MultiSearchPlayer.act, bit-identical command hash).
  The cutoff default (`fallback`) is the R3a poll, as in K4C, unless the caller passes `default=`.
- LivePlayer: the Player facade the live loop and bot.eval.headline both drive.
    tier='search': it5s2 polls every 5 ticks (D1 tracking), then WallCandidatePlayer decides on 10-tick
                   multiples with it5s2's action as its cutoff default ('it5s2' default) or R3a's ('R3a').
                   If the search raises, it5s2's action is used (source='fast-error'); after
                   `max_errors` consecutive errors the search tier is disabled for the match.
    tier='fast':   pure it5s2 (bot/exit/student.py StudentPlayer decode: top-1 legal play when
                   P(play) >= 0.5375, else WAIT), every 5 ticks.
  Every Decision carries stats: source, wall/cpu ms, search hit/completed/candidates, both tiers' actions.

Actions are the seat's own frame: slot*576 + row*18 + col, WAIT = 2304 (bot/players/base.py).
Deterministic only with wall_ms=None (no clock enters a decision); wall mode is not reproducible.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from bot.players.base import Decision, MatchContext, PublicView, SEARCH_INTERVAL, WAIT
from bot.players.search import RETURN_RESERVE
from bot.search.candidates import CandidateSearchPlayer
from bot.search.players import MultiSearchPlayer, planner_class as multi_planner_class

FAST_DEFAULT = os.environ.get(
    'CLASHER_LIVE_FAST', 'student:/mpac/sdicks02/repos/clasher-bot-runtime/students/it5s2-step001200.pt@0.5375')
FAST_SHA256 = '08bdaf32fb5bde9b057b49129cadfd926bc19a49428722f9f9d49c765d55cc5b'


def wall_planner_class():
    """K4C's MultiRootPlanner; given a deadline it delegates to the frozen K4S kernel (deadline + threads)."""
    import sdefault
    from delay import DelayAwarePlanner
    kernel = sdefault.planner_class(DelayAwarePlanner)
    multi = multi_planner_class(kernel, sdefault.apply_default)

    class WallPlanner(multi):
        def score_candidates(self, root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
            if deadline is None:
                return super().score_candidates(root, seat, candidates, trace=trace, deadline=None,
                                                fallback=fallback)
            if len(self.roots) > 1:
                raise ValueError('wall mode supports one determinization (K4C roots=1)')
            # sdefault.Planner.score_candidates -> anchor.anytime(threads=search_threads) -> apply_default
            return kernel.score_candidates(self, root, seat, candidates, trace=trace, deadline=deadline,
                                           fallback=fallback)
    return WallPlanner


class _WallMulti(MultiSearchPlayer):
    """MultiSearchPlayer.start/act with SearchPlayer's wall-mode deadline handling (roots=1 only)."""
    wall_ms = None
    threads = 1
    root_fn = None     # optional level-aware root (bot/live/levels.py); None = the frozen R.root

    def set_deadline(self, wall_ms, threads):
        if wall_ms is None:
            if threads != 1:
                raise ValueError('the unbounded (deterministic) search uses one scoring thread')
        elif wall_ms <= 1000*RETURN_RESERVE:
            raise ValueError('wall_ms must exceed the 8 ms return reserve')
        if threads not in (1, 2, 4):
            raise ValueError('the K kernel supports 1, 2 or 4 scoring threads')
        if self.roots != 1 or self.budget is not None:
            raise ValueError('wall mode is defined for K4C (roots=1, no rollout budget)')
        self.wall_ms, self.threads = wall_ms, threads
        self.deadline_seconds = None if wall_ms is None else wall_ms/1000

    def start(self, ctx: MatchContext):
        # MultiSearchPlayer.start with the wall planner and search_threads=self.threads.
        rt, R = self.rt, self.rt.R
        from fair_player import PublicPlanner
        from clasher.rl.c56_rollout_planner import C56SearchConfig
        from belief import Belief
        from bot.players.policy import make_poller
        seed = ctx.seed + 100000
        p = PublicPlanner(R, rt.PRIOR, seed)
        p.belief.__class__ = Belief
        p.core = wall_planner_class()(
            R.builder, R.bots, backend='native', seed=seed+1, native=R.native, native_config=R.config,
            catalog=rt.CAT,
            config=C56SearchConfig(samples=self.samples, threads=1, horizon=self.horizon, wait_screen8=False),
            command_delay=ctx.command_delay, delay_aware=True, symmetric_opponent=True,
            opponent_delay=ctx.opponent_delay, opponent_interval=10, opponent_capacity=1,
            max_outstanding=1, arm='W', variant='screen8', reserve_floor=False,
            search_threads=self.threads, coarse_horizon=self.horizon)
        p.core.rollout_budget = self.budget
        self.p, self.seed = p, seed
        self.poller, self.cached = make_poller(rt, ctx, 'R3a')

    def act(self, view: PublicView, *, wall0=None, default=None) -> Decision:
        """wall0: decision start (monotonic) the deadline counts from; default: cutoff default action
        (None = the R3a poll, as K4C). With wall_ms=None this is MultiSearchPlayer.act verbatim."""
        if self.deadline_seconds is None and default is None and self.root_fn is None:
            return MultiSearchPlayer.act(self, view)
        p, R, info = self.p, self.rt.R, view.info
        wall0 = time.monotonic() if wall0 is None else wall0
        fallback = int(self.poller.poll(view.tick, view.reserved.packet, view.public_events))
        fallback = fallback if fallback < WAIT else WAIT
        if not view.can_act or view.tick % SEARCH_INTERVAL:
            return Decision(WAIT, stats=None)
        if default is not None:
            fallback = int(default) if int(default) < WAIT else WAIT
        cutoff = None if self.deadline_seconds is None else wall0+self.deadline_seconds-RETURN_RESERVE
        try:
            p.belief.update(info.tick, info.events, deadline=cutoff)
        except TimeoutError:
            p.core.selected_wait_ticks = 0
            return self._done(fallback, dict(hit=True, fallback=True, preparation_cutoff='belief'), wall0)
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
        if cutoff is not None and time.monotonic() >= cutoff:
            p.core.selected_wait_ticks = 0
            return self._done(fallback, dict(hit=True, fallback=True, candidates=len(candidates),
                                             preparation_cutoff='candidates'), wall0)
        try:
            opponent = p.belief.sample(p.rng, deadline=cutoff)
        except TimeoutError:
            p.core.selected_wait_ticks = 0
            return self._done(fallback, dict(hit=True, fallback=True, preparation_cutoff='sample'), wall0)
        root = (self.root_fn or R.root)(info, opponent, p.rng)
        p.core.roots = [root]
        try:
            action = p.core.score_candidates(root, view.seat, candidates, deadline=cutoff, fallback=fallback)
        finally:
            p.core.roots = ()
        stats = dict(p.core.deadline_stats or {})
        stats.setdefault('candidates', len(candidates))
        return self._done(int(action), stats, wall0, p.core.selected_wait_ticks)


class WallCandidatePlayer(CandidateSearchPlayer, _WallMulti):
    """K4C-r<r3a> with a wall deadline: 'K4CW-r16-w200-t4'. wall_ms=None: exactly K4C-r<r3a>."""

    def __init__(self, rt, *, r3a=16, wall_ms=200, threads=4, name=None):
        super().__init__(rt, r3a=r3a, second=0, second_path=None,
                         name=name or wall_name(r3a, wall_ms, threads))
        self.set_deadline(wall_ms, threads)


def wall_name(r3a, wall_ms, threads):
    return f'K4CW-r{r3a}' + ('' if wall_ms is None else f'-w{wall_ms}-t{threads}')


def parse_wall_name(name):
    """'K4CW-r16-w200-t4' -> dict(r3a=16, wall_ms=200, threads=4); 'K4CW-r16' -> unbounded."""
    import re
    m = re.fullmatch(r'K4CW-r(\d+)(?:-w(\d+)-t(\d+))?', name)
    if not m:
        raise ValueError(f'bad K4CW name {name!r}')
    return dict(r3a=int(m[1]), wall_ms=int(m[2]) if m[2] else None, threads=int(m[3]) if m[3] else 1)


def live_belief_class():
    """s1 Belief that never raises on an off-prior opponent deck (random/low-arena decks): when no prior deck is
    consistent with the public plays, the prior is rebuilt as the human decks COMPLETED with the revealed cards
    (revealed + the deck's remaining cards in catalog order, weights summed, top `max_decks`) and the whole event
    history is replayed. Costs ~0.1-1 s once per rebuild (no deadline); counted in `rebuilds`."""
    from belief import Belief

    class LiveBelief(Belief):
        max_decks = 400
        rebuilds = 0
        human_prior = None

        def update(self, tick, events, *, deadline=None, clock=time.monotonic):
            try:
                return super().update(tick, events, deadline=deadline, clock=clock)
            except ValueError as ex:
                if 'no train deck' not in str(ex):
                    raise
            self._pending = None
            revealed = list(dict.fromkeys(e.name for e in events if e.kind == 'card'))
            prior = completed_prior(self.human_prior, revealed, self.max_decks)
            keep = (self.human_prior, self.max_decks, self.rebuilds + 1)
            Belief.__bases__[0].__init__(self, prior, self.costs)    # frozen DerivedPublicState.__init__
            self.human_prior, self.max_decks, self.rebuilds = keep
            return super().update(tick, events)
    return LiveBelief


def completed_prior(prior, revealed, max_decks=400):
    if len(revealed) > 8:
        raise ValueError('more than 8 distinct revealed cards')
    weights = {}
    for d in prior['decks']:
        deck = tuple(sorted(revealed + [c for c in d['cards'] if c not in revealed][:8-len(revealed)]))
        weights[deck] = weights.get(deck, 0.) + float(d.get('frequency', d.get('sampling_weight', 1.)))
    top = sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))[:max_decks]
    return dict(decks=[dict(cards=list(k), frequency=w) for k, w in top])


def load_fast(rt, spec=FAST_DEFAULT, *, verify=True):
    from bot.exit.student import StudentPlayer, parse_spec
    path, _ = parse_spec(spec)
    if verify and Path(path).name == 'it5s2-step001200.pt':
        from bot.players.runtime import sha256
        if sha256(path) != FAST_SHA256:
            raise ValueError(f'{path}: sha256 != it5s2 pin {FAST_SHA256}')
    return StudentPlayer.from_spec(rt, spec)


class LivePlayer:
    """Player facade: start(ctx), act(view) / decide(view) -> Decision, close()."""

    def __init__(self, rt, *, tier='search', wall_ms=200, threads=4, r3a=16, fast_spec=FAST_DEFAULT,
                 cutoff_default='it5s2', max_errors=3, levels=None, name=None):
        if tier not in ('search', 'fast'):
            raise ValueError(tier)
        if cutoff_default not in ('it5s2', 'R3a'):
            raise ValueError(cutoff_default)
        self.rt, self.tier, self.cutoff_default, self.max_errors = rt, tier, cutoff_default, max_errors
        self.fast = load_fast(rt, fast_spec)
        self.search = WallCandidatePlayer(rt, r3a=r3a, wall_ms=wall_ms, threads=threads) if tier == 'search' else None
        self.deadline_seconds = self.search.deadline_seconds if self.search else None
        if self.search is not None and levels is not None and not levels.trivial():
            from bot.live.levels import LevelRoot
            self.search.root_fn = LevelRoot(rt.R, levels).root
        self.name = name or ('LIVE-fast-it5s2' if tier == 'fast' else
                             f'LIVE-{self.search.name}' + ('' if cutoff_default == 'it5s2' else '-dR3a'))
        self.decisions = []

    def start(self, ctx: MatchContext):
        self.ctx, self.errors, self.search_disabled = ctx, 0, False
        self.fast.start(ctx)
        if self.search is not None:
            self.search.start(ctx)
            belief = self.search.p.belief
            belief.__class__ = live_belief_class()
            belief.human_prior = self.rt.PRIOR

    def act(self, view: PublicView) -> Decision:
        wall0, cpu0 = time.monotonic(), time.process_time()
        try:
            fast = self.fast.act(view).action     # polls every 5 ticks (D1 state); WAIT off-cadence
        except Exception as ex:                   # a broken fast poller must not stop the search tier
            self.fast_errors = getattr(self, 'fast_errors', 0) + 1
            if self.search is None:
                if not view.can_act:
                    return Decision(WAIT, stats=None)
                return self._done(Decision(WAIT), 'fast-error', wall0, cpu0, fast=WAIT, error=repr(ex)[:300])
            fast = WAIT
        if self.search is None:
            if not view.can_act:
                return Decision(WAIT, stats=None)
            return self._done(Decision(fast), 'fast', wall0, cpu0, fast=fast)
        if self.search_disabled:
            if not view.can_act or view.tick % SEARCH_INTERVAL:
                return Decision(WAIT, stats=None)
            return self._done(Decision(fast), 'fast-disabled', wall0, cpu0, fast=fast)
        default = fast if self.cutoff_default == 'it5s2' else None
        try:
            d = self.search.act(view, wall0=wall0, default=default)
        except Exception as ex:   # never refuse to act: it5s2 decides, the error is recorded
            if not view.can_act or view.tick % SEARCH_INTERVAL:
                return Decision(WAIT, stats=None)
            self.errors += 1              # consecutive failed DECISIONS (off-cadence polls do not count)
            self.search_disabled = self.errors >= self.max_errors
            return self._done(Decision(fast), 'fast-error', wall0, cpu0, fast=fast, error=repr(ex)[:300])
        if d.stats is None:
            return d
        self.errors = 0
        s = d.stats
        defaulted = bool(s.get('fallback')) or bool(s.get('student_default')) or 'preparation_cutoff' in s
        source = 'search' if not defaulted else f'default-{self.cutoff_default}'
        return self._done(d, source, wall0, cpu0, fast=fast, search=s)

    decide = act

    def _done(self, d, source, wall0, cpu0, *, fast, search=None, error=None):
        stats = dict(source=source, action=int(d.action), fast_action=int(fast),
                     belief_rebuilds=getattr(self.search.p.belief, 'rebuilds', 0) if self.search else 0,
                     wall_ms=1000*(time.monotonic()-wall0), cpu_ms=1000*(time.process_time()-cpu0))
        if search is not None:
            stats.update({k: search.get(k) for k in ('hit', 'completed', 'candidates', 'rollouts',
                                                     'student_default', 'preparation_cutoff')
                          if search.get(k) is not None})
            stats['search_wall_ms'] = 1000*search['wall_seconds']
        if error is not None:
            stats['error'] = error
        self.decisions.append(stats)
        return Decision(int(d.action) if d.action < WAIT else WAIT, int(d.wait_ticks), stats)

    def close(self):
        if self.search is not None:
            self.search.close()


def make_live_player(rt, name):
    """Names for bot.eval / bot.live runners:
    'K4CW-r16[-w<ms>-t<threads>]'      the wall search alone (cutoff default R3a, as K4C)
    'LIVE-K4CW-r16-w<ms>-t<threads>'   LivePlayer search tier (cutoff default it5s2); suffix '-dR3a' for R3a
    'LIVE-fast-it5s2'                  LivePlayer pure it5s2
    'PERC-<arm>:<name>'                <name> seeing the game only through synthetic perception at noise <arm>
    Anything else -> bot.eval.headline.make_player."""
    if name.startswith('PERC-'):     # 'PERC-<noise arm>:<player name>' (bot/live/perc.py)
        from bot.live.perc import PercPlayer
        arm, _, inner = name[5:].partition(':')
        return PercPlayer(rt, arm, make_live_player(rt, inner))
    if name.startswith('K4CW-'):
        return WallCandidatePlayer(rt, **parse_wall_name(name))
    if name == 'LIVE-fast-it5s2':
        return LivePlayer(rt, tier='fast')
    if name.startswith('LIVE-K4CW-'):
        body, dflt = (name[5:-5], 'R3a') if name.endswith('-dR3a') else (name[5:], 'it5s2')
        kw = parse_wall_name(body)
        return LivePlayer(rt, tier='search', cutoff_default=dflt, **kw)
    return _HEADLINE_MAKE_PLAYER(rt, name)


from bot.eval.headline import make_player as _HEADLINE_MAKE_PLAYER   # captured before headline_wall patches it
