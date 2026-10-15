"""Live (pooled, wall-deadline) multi-root K4L: learned sample j > 0 from its own determinized root (lever (b)).

    'LIVE-MRK<n>-D-w<ms>-t<N>-p<P>'
        = LIVE-K4L-R-gs-rw-fc-w<ms>-t<N>-p<P> (bot/search/lopp_fast.py make_live_lopp) with token K<n> (n learned
        samples averaged) and token D (lopp.py: sample j > 0 runs from a root built on its OWN belief sample of the
        opponent's hidden hand/cycle, rng keyed (seed, tick, j, 0xD); sample 0 and the native scan use the planner's
        root). lopp.py defines D for the serial reduction only; here the extra roots are shipped to the pool
        workers ('rootj' message, same snapshot encoding as the main root), so with rw the values equal the serial
        twin's (bot/noise/multiroot.py LIVEMR-K<n>-D). Without w<ms> ('LIVE-MRK<n>-D-t1-p4' is not defined; the
        twin is the serial arm).
Nothing in bot/search is edited: the worker loop is lopp_fast._pool_worker plus the 'rootj' message, and the pool is
LearnedPool with that worker and the extra roots sent right after begin().
"""
from __future__ import annotations

import importlib
import re
import time

import numpy as np

from bot.players.base import WAIT


def _mr_pool_worker(conn, native, spawn=None):
    """lopp_fast._pool_worker + ('rootj', gen, j, snapshot): learned sample j of decision `gen` runs from that root."""
    from bot.search.lopp import batch_rollouts, fatal, load_model
    from bot.search.lopp_fast import ConfigCache, opponent_from_spec
    if spawn is not None:
        module, meta, models = spawn
        native = importlib.import_module(module).NativeScripts(meta)
        for name in models:
            load_model(name)
    state_class = importlib.import_module(type(native).__module__).BattleState
    root = seat = kw = opp = cutoff = configs = root_err = None
    roots = {}
    gen, t_parse = -1, 0.

    def parse(snap):
        return state_class(snap if isinstance(snap, str) else configs.payload(*snap))
    while True:
        try:
            msg = conn.recv()
        except EOFError:
            return
        if msg[0] == 'config':
            configs = ConfigCache(msg[1])
        elif msg[0] == 'root':
            _, gen, snap, seat, kw, opp, cutoff = msg
            roots = {}
            t0 = time.monotonic()
            try:
                root, root_err = parse(snap), None
            except BaseException as ex:
                if fatal(ex):
                    raise
                root, root_err = None, f'root: {ex!r:.300}'
            t_parse = time.monotonic() - t0
        elif msg[0] == 'rootj':
            _, g, j, snap = msg
            if g == gen:
                t0 = time.monotonic()
                try:
                    roots[j] = (parse(snap), None)
                except BaseException as ex:
                    if fatal(ex):
                        raise
                    roots[j] = (None, f'rootj: {ex!r:.300}')
                t_parse += time.monotonic() - t0
        elif msg[0] == 'run':
            _, g, cid, keys = msg[:4]
            j = msg[4] if len(msg) > 4 else 0
            c0, w0 = time.process_time(), time.monotonic()
            vals = err = None
            r, rerr = roots.get(j, (root, root_err)) if j else (root, root_err)
            if g == gen and rerr is not None:
                err = rerr
            elif g == gen and (cutoff is None or time.monotonic() < cutoff):
                try:
                    opponent = opp if isinstance(opp, str) else opponent_from_spec(opp, j)
                    vals = batch_rollouts(native, r, seat, keys, opponent, deadline=cutoff, **kw)
                except BaseException as ex:
                    if fatal(ex):
                        raise
                    vals, err = None, repr(ex)[:300]
            conn.send(('done', g, cid, vals, time.process_time() - c0, time.monotonic() - w0, t_parse, err))
        else:
            return


def _pool_class():
    from bot.search.lopp_fast import LearnedPool, split_snapshot

    class MRPool(LearnedPool):
        """LearnedPool whose workers run _mr_pool_worker; `extra` = {j: root} is shipped after each begin()."""

        def __init__(self, n, native, model_names=(), meta=None, config=None):
            import bot.search.lopp_fast as lf
            orig = lf._pool_worker
            lf._pool_worker = _mr_pool_worker       # LearnedPool.__init__ reads the module global at call time
            try:
                super().__init__(n, native, model_names, meta, config)
            finally:
                lf._pool_worker = orig
            self.extra = {}

        def begin(self, root, seat, kw, opp, cutoff):
            super().begin(root, seat, kw, opp, cutoff)
            t0 = time.monotonic()
            for j, r in sorted(self.extra.items()):
                snap = r.snapshot()
                parts = split_snapshot(snap)
                msg = snap if parts is None or not self.base_sent and parts[1] != self.config else (parts[0], parts[2])
                self._send_all(('rootj', self.gen, j, msg))
            self.timing['ship_extra'] = time.monotonic() - t0
    return MRPool


_MR_POOLS = {}


def get_mr_pool(n, native, model_name, meta=None, config=None):
    import json
    from bot.search.lopp import FAILURES
    if n in _MR_POOLS and (_MR_POOLS[n].broken or not all(p.is_alive() for p in _MR_POOLS[n].procs)):
        _MR_POOLS.pop(n).close()
        FAILURES['pool_recreated'] += 1
    if n not in _MR_POOLS:
        if meta is not None and not isinstance(meta, str):
            meta = json.dumps(meta)
        _MR_POOLS[n] = _pool_class()(n, native, tuple(model_name.split('+')), meta, config)
    return _MR_POOLS[n]


def make_live_mr(rt, name):
    import sdefault
    from bot.live.player import LivePlayer
    from bot.search.lopp import load_model
    from bot.search.lopp_fast import install_fast_prep, opponent_from_spec, reduce_fast, wall_player_class
    from bot.search.oppmodel import TIMED_WAITS
    m = re.fullmatch(r'LIVE-MRK(\d+)-D-w(\d+)-t(\d+)-p(\d+)', name)
    if not m:
        raise ValueError(f'bad live multi-root name {name!r}')
    K, wall_ms, threads, P = (int(x) for x in m.groups())
    WL = wall_player_class()

    class LiveMR(WL):
        def start(self, ctx):
            get_mr_pool(P, self.rt.R.native, self.model_name, getattr(self.rt.R, 'meta', None), self.rt.R.config)
            self.pool_size = 0                      # WL.start must not fork the plain pool
            super().start(ctx)
            self.pool_size = P
            install_fast_prep(self.rt, cut=True)
            core, R, seed = self.p.core, self.rt.R, ctx.seed
            names = self.model_name.split('+')
            for n_ in names:
                load_model(n_)
            mr = self

            def spec():
                return dict(model=names[0], models=names, sample=self.sample, switch=self.switch,
                            interval=self.interval, seed=[seed, int(core.info.tick)], rowwise=self.rowwise,
                            bias=self.bias, own=False, offset=0)

            def score_candidates(root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
                pool = get_mr_pool(P, core.native, self.model_name, getattr(R, 'meta', None), R.config)
                t0 = time.monotonic()
                extra = {}
                for j in range(1, K):
                    rng = np.random.default_rng([seed, int(core.info.tick), j, 0xD])
                    extra[j] = R.root(core.info, mr.p.belief.sample(rng), rng)
                pool.extra = extra
                prep = time.monotonic() - t0
                action, info = reduce_fast(core, root, seat, candidates, make_opp=lambda j=0: opponent_from_spec(spec(), j),
                                           opp_spec=spec(), threads=threads, pool=pool, deadline=deadline,
                                           coarse_order=core.coarse_order, refine_proposals=core.refine_proposals,
                                           samples=K)
                pool.extra = {}
                info.setdefault('phase_ms', {})['extra_roots'] = round(1e3*prep, 2)
                action = fallback if action is None else action
                core.selected_wait_ticks = TIMED_WAITS.get(action, 0)
                action = sdefault.apply_default(core, action, fallback, candidates)
                core.deadline_stats['rollouts'] = info['rollouts']
                self._dec = info
                return action
            core.score_candidates = score_candidates
            self._dec = {}

    search = LiveMR(rt, wall_ms=wall_ms, threads=threads, pool=P, model='pool', sample=True, rowwise=True,
                    fast_prep=True, fast_cut=True, arm=dict(kind='R', samples=K), name=name[5:])
    live = LivePlayer(rt, tier='search', wall_ms=wall_ms, threads=threads, cutoff_default='it5s2', name=name)
    live.search = search
    return live
