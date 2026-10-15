"""K4L-R under a wall budget: threaded native rollouts, learned rollouts in persistent worker processes (exploration).

K4L-R-gs (bot/search/lopp.py) spends its decision on ~22 native balanced rollouts (coarse scan + waits) and ~11
Python-driven learned-opponent rollouts (WAIT, timed waits, top-8 plays). The pinned native releases the GIL in
rollout_e1 but not in BattleState.step / NativeScripts.* (the `gil-release` cargo feature is off in 44874fd6), so
the learned loop does not scale with threads. Tokens added to 'K4L-R...' names (kind R only):

- t<N>  native rollouts on N threads (1, 2 or 4; rollout_e1 on a private clone, as the frozen anchor.anytime).
        Values are unchanged: with no other token this is K4L-R bit for bit (same 11-key learned batch).
- rw    (lopp.py) row-wise opponent forward: values do not depend on batching, so with rw every c/p split
        gives exactly the unchunked serial values (K4L-R-gs-rw is the serial twin of K4L-R-gs-rw-t4-p4).
- c<P>  learned rollouts in fixed chunks: the waits (WAIT, 2401, 2402 present) as one lockstep batch, the chosen
        plays (in candidate order) round-robin into P batches. Serial, in this process. The opponent net's float32
        forward depends on the batch composition (numpy/BLAS), so chunking changes values in the low bits; c<P> is
        the serial twin that defines the chunked arm's values.
- p<P>  the same chunks run in P persistent worker processes (forked once per process; the root is shipped as
        BattleState.snapshot(), exact: serde float_roundtrip). The waits chunk goes to worker 0 at the start of
        the decision, concurrently with the native coarse scan; play chunk j goes to worker j. p<P> == c<P>.
- fp    output-identical preparation caches (install_fast_prep): the root payload's config JSON and the repeated
        R3a forward of the r16 candidate list. Deterministic arms with and without fp have equal command hashes.
        Only the snapshot's dynamic part (~60 KB) travels per decision; workers hold the config (sent once) and
        rebuild the root with only the deck cards (ConfigCache; 1.1 vs 7.1 ms to parse).
- w<ms> wall deadline through bot/live/player.py's WallCandidatePlayer (cutoff = start + ms - 8 ms reserve;
        preparation cutoffs as K4CW). At the cutoff only keys with both a balanced and a learned value count;
        if no play is complete the S-default rule plays the cutoff default (R3a, or it5s2 under LIVE-).
        Requires t<N> (sets the K kernel's thread count too).
Examples: K4L-R-gs-t4 (== K4L-R-gs), K4L-R-gs-c4 (serial twin), K4L-R-gs-t4-p4, K4L-R-gs-w200-t4-p4,
LIVE-K4L-R-gs-w200-t4-p4 (LivePlayer search tier with this search; it5s2 fast tier and cutoff default).
Without w<ms> nothing reads the clock, so every arm is deterministic.
"""
from __future__ import annotations

import importlib
import multiprocessing as mp
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from multiprocessing.connection import wait as wait_conns

from bot.players.base import WAIT
from bot.search.lopp import Learned, LearnedOppPlayer, batch_rollouts, load_model
from bot.search.oppmodel import STYLES, TIMED_WAITS, _argmax, _bonus

_POOLS: dict = {}
_EXECUTORS: dict = {}


def split_snapshot(snap):
    """BattleState.snapshot() -> (head, config text, tail): serde writes `"config":{...}` just before
    `,"pending_casts":` (fields in struct order). None if the layout is not found."""
    i = snap.rfind('"config":')
    j = snap.rfind(',"pending_casts":')
    if i < 0 or j < i:
        return None
    return snap[:i + 9], snap[i + 9:j], snap[j:]


class ConfigCache:
    """Rebuilds a root from (head, tail) and a cached config, keeping only the cards in either player's hand or
    cycle (the only cards a rollout can play). The cut config is re-serialized by Python's json (shortest
    round-trip floats; the native parses with float_roundtrip), so the values are exact; lopp_fast_check
    verifies every rollout value on such roots against the original root."""

    def __init__(self, text):
        import json
        cfg = json.loads(text)
        self.other = json.dumps({k: v for k, v in cfg.items() if k != 'cards'})[1:-1]
        self.cards = {n: json.dumps(n) + ':' + json.dumps(v) for n, v in cfg['cards'].items()}
        self.cut = {}

    def payload(self, head, tail):
        import json
        players = json.loads(head[head.index('"players":') + 10:head.index(',"entities":')])
        need = tuple(sorted({c for p in players for c in p['hand'] + p['cycle'] if c in self.cards}))
        if need not in self.cut:
            self.cut[need] = '{' + self.other + ',"cards":{' + ','.join(self.cards[n] for n in need) + '}}'
        return head + self.cut[need] + tail


def _pool_worker(conn, native):
    """Worker loop: ('root', gen, snapshot, seat, kw, opp, cutoff) then ('run', gen, cid, keys) -> ('done', ...)."""
    state_class = importlib.import_module(type(native).__module__).BattleState
    root = seat = kw = opp = cutoff = configs = None
    gen, t_parse = -1, 0.
    while True:
        try:
            msg = conn.recv()
        except EOFError:
            return
        if msg[0] == 'config':
            configs = ConfigCache(msg[1])
        elif msg[0] == 'root':
            _, gen, snap, seat, kw, opp, cutoff = msg
            t0 = time.monotonic()
            root = state_class(snap if isinstance(snap, str) else configs.payload(*snap))
            t_parse = time.monotonic() - t0
        elif msg[0] == 'run':
            _, g, cid, keys = msg
            c0, w0 = time.process_time(), time.monotonic()
            vals = None
            if g == gen and (cutoff is None or time.monotonic() < cutoff):
                opponent = opp if isinstance(opp, str) else Learned(   # a style name: exactness checks
                    load_model(opp['model']), opp['sample'], opp['switch'], opp['interval'], seed=opp['seed'],
                    rowwise=opp.get('rowwise', False))
                vals = batch_rollouts(native, root, seat, keys, opponent, deadline=cutoff, **kw)
            conn.send(('done', g, cid, vals, time.process_time() - c0, time.monotonic() - w0, t_parse))
        else:
            return


class LearnedPool:
    """P forked worker processes holding the native scripts and the opponent nets (loaded before the fork)."""

    def __init__(self, n, native, model_names=()):
        for name in model_names:
            load_model(name)
        ctx = mp.get_context('fork')
        self.conns, self.procs = [], []
        for _ in range(n):
            here, there = ctx.Pipe()
            proc = ctx.Process(target=_pool_worker, args=(there, native), daemon=True)
            proc.start()
            there.close()
            self.conns.append(here)
            self.procs.append(proc)
        self.gen = 0
        self.pending, self.results, self.cpu = {}, {}, 0.
        self.timing = {}
        self.config = None

    def begin(self, root, seat, kw, opp, cutoff):
        self.gen += 1
        self.pending, self.results, self.cpu = {}, {}, 0.
        self.timing = dict(parse=0., chunk=0.)
        snap = root.snapshot()
        parts = split_snapshot(snap)
        if parts is not None and parts[1] != self.config:    # new config (first root, level scaling): once
            self.config = parts[1]
            for conn in self.conns:
                conn.send(('config', self.config))
        msg = snap if parts is None else (parts[0], parts[2])
        for conn in self.conns:
            conn.send(('root', self.gen, msg, seat, kw, opp, cutoff))

    def submit(self, worker, cid, keys):
        self.conns[worker].send(('run', self.gen, cid, list(keys)))
        self.pending[cid] = worker

    def collect(self, cutoff=None):
        """Wait for every pending chunk (or the cutoff); returns {cid: values or None}."""
        while self.pending:
            remaining = None if cutoff is None else cutoff - time.monotonic()
            if remaining is not None and remaining <= 0:
                break
            busy = [self.conns[w] for w in set(self.pending.values())]
            for conn in wait_conns(busy, timeout=remaining):
                _, gen, cid, vals, cpu, wall, parse = conn.recv()
                if gen != self.gen:
                    continue                      # a chunk abandoned at an earlier decision's cutoff
                self.cpu += cpu
                self.timing['parse'] = max(self.timing['parse'], parse)
                self.timing['chunk'] = max(self.timing['chunk'], wall)
                self.pending.pop(cid, None)
                self.results[cid] = vals
        return self.results

    def close(self):
        for conn in self.conns:
            try:
                conn.send(('stop',))
            except (BrokenPipeError, OSError):
                pass
        for proc in self.procs:
            proc.join(timeout=1)


class _ConfigJson:
    """Stands in for `json` in fair_player / bot.live.levels: dumps(dict(..., config=R.config)) with config as the
    last key returns json.dumps(rest)[:-1] + ', "config": ' + <cached json.dumps(R.config)> + '}', byte for byte
    what json.dumps would return (default separators), without re-serializing the 2 MB catalogue each root."""

    def __init__(self, config, verify):
        import json
        self._json, self._config, self._verify = json, config, verify
        self._text = json.dumps(config)
        self.hits = 0

    def __getattr__(self, name):
        return getattr(self._json, name)

    def dumps(self, obj, *args, **kw):
        if args or kw or type(obj) is not dict or obj.get('config') is not self._config or list(obj)[-1] != 'config':
            return self._json.dumps(obj, *args, **kw)
        rest = self._json.dumps({k: v for k, v in obj.items() if k != 'config'})
        text = (rest[:-1] + ', ' if len(rest) > 2 else '{') + '"config": ' + self._text + '}'
        if self._verify and text != self._json.dumps(obj):
            raise AssertionError('fast-prep json differs')
        self.hits += 1
        return text


def install_fast_prep(rt):
    """Token fp: output-identical preparation caches, process-wide and idempotent.
    1. Resources.root (and bot.live.levels.LevelRoot) json.dumps of the config -> _ConfigJson.
    2. proposals.outputs memo: K4C-r16's candidate list re-runs R3a's forward (bot/search/candidates.py ranked,
       r3a=16 > the poller's cached 8) on the same features the poller just used; an identical feature batch
       (every tensor torch.equal, same model) returns the previous outputs.
    CLASHER_FASTPREP_VERIFY=1 recomputes both the slow way and raises on any difference."""
    import os
    import sys
    if getattr(rt, '_fast_prep', False):
        return
    verify = os.environ.get('CLASHER_FASTPREP_VERIFY') == '1'
    shim = _ConfigJson(rt.R.config, verify)
    for mod in (type(rt.R).root.__module__, 'bot.live.levels'):
        if mod == 'bot.live.levels':
            importlib.import_module(mod)
        sys.modules[mod].json = shim
    import cached_policy
    import proposals
    import torch
    slow, last = proposals.outputs, {}

    def outputs(model, b):
        prev = last.get('key')
        if prev is not None and prev[0] is model and prev[1].keys() == b.keys() and all(
                torch.equal(prev[1][k], b[k]) for k in b):
            out = last['out']
            last['hits'] = last.get('hits', 0) + 1
            if verify:
                ref = slow(model, b)
                if not all(torch.equal(x, y) for x, y in zip(ref, out)):
                    raise AssertionError('fast-prep outputs memo differs')
            return out
        out = slow(model, b)
        last.update(key=(model, {k: v.clone() for k, v in b.items()}), out=out)
        return out
    proposals.outputs = cached_policy.outputs = outputs
    rt._fast_prep = True
    rt._fast_prep_stats = lambda: dict(json_hits=shim.hits, memo_hits=last.get('hits', 0))


def get_pool(n, native, model_name):
    """One pool per process (forked once, before any thread pool exists in this process)."""
    if n not in _POOLS:
        _POOLS[n] = LearnedPool(n, native, (model_name,))
    return _POOLS[n]


def get_executor(n):
    if n not in _EXECUTORS:
        _EXECUTORS[n] = ThreadPoolExecutor(max_workers=n)
    return _EXECUTORS[n]


def chunk_keys(keys, parts):
    """K4L-R learned keys -> [waits batch] + `parts` round-robin play batches (empty batches dropped)."""
    waits = [k for k in keys if k >= WAIT]
    plays = [k for k in keys if k < WAIT]
    groups = [plays[j::parts] for j in range(parts)]
    return [('w', waits)] * bool(waits) + [(j, g) for j, g in enumerate(groups) if g]


def reduce_fast(core, root, seat, candidates, *, make_opp, opp_spec, threads=1, chunks=0, pool=None,
                deadline=None, coarse_order=(), refine_proposals=()):
    """lopp.reduce_learned for kind R, with threaded native rollouts, chunked/pooled learned rollouts, cutoff."""
    original = list(candidates)
    if WAIT not in original or len(set(original)) != len(original):
        raise ValueError('unique candidates including WAIT required')
    plays = [a for a in original if a < WAIT]
    hinted = list(dict.fromkeys(a for a in coarse_order if a in plays))
    scan = hinted + [a for a in plays if a not in hinted]
    cfg = core.config
    kw = dict(delay=core.command_delay, opp_delay=core.opponent_delay, horizon=cfg.horizon,
              interval=cfg.interval, elixir_weight=cfg.elixir_weight, tick0=int(core.info.tick))
    native = core.native
    hit = False
    waits = [a for a in original if a >= WAIT and a != 2400]

    def expired():
        return deadline is not None and time.monotonic() >= deadline

    def rollout(a):
        private = root.clone() if threads > 1 else root
        budget = 1e6 if deadline is None else deadline - time.monotonic()
        if budget <= 0:
            return None
        try:
            v = native.rollout_e1(private, seat, a, STYLES[0], core.command_delay, core.opponent_delay,
                                  cfg.horizon, cfg.interval, cfg.elixir_weight, budget)
        except TimeoutError:          # rollout_e1 past its budget ('E1 wall deadline')
            return None
        return None if expired() else v

    # Native balanced values: waits first (the K kernel's order), then the coarse scan.
    nat = {}
    todo = waits + scan
    t0 = time.monotonic()
    tm = {}
    if threads > 1:
        ex = get_executor(threads)
        futs = {ex.submit(rollout, a): a for a in todo}
    if pool is not None:      # ship the root while the native threads run (rollout_e1 releases the GIL)
        pool.begin(root, seat, kw, opp_spec, deadline)
        pool.submit(0, 'w', waits)
        tm['ship'] = time.monotonic() - t0
    if threads == 1:
        for a in todo:
            v = rollout(a)
            if v is None:
                hit = True
                break
            nat[a] = v
    else:
        remaining = None if deadline is None else max(0., deadline - time.monotonic())
        done, rest = wait(futs, timeout=remaining)
        for f in rest:
            f.cancel()
        hit = bool(rest)
        for f in done:
            v = f.result()
            if v is None:
                hit = True
            else:
                nat[futs[f]] = v
    n_native = len(nat)
    tm['native'] = time.monotonic() - t0
    L, n_learned, first = {}, 0, {}
    if all(a in nat for a in scan):
        first = {a: 0. + nat[a] for a in scan}
        chosen = set(sorted(plays, key=lambda a: (-first[a], original.index(a)))[:8])
        chosen.update(a for a in refine_proposals if a in plays)
        work = [a for a in original if a >= WAIT or a in chosen]
        keys = [a for a in original if (a >= WAIT and a != 2400) or a in chosen]
        if pool is not None:
            parts = chunk_keys(keys, len(pool.conns))
            for cid, group in parts:
                if cid != 'w':
                    pool.submit(cid, cid, group)
            results = pool.collect(deadline)
        else:
            parts = chunk_keys(keys, chunks) if chunks else [('all', list(dict.fromkeys(keys)))]
            results = {}
            for cid, group in parts:
                results[cid] = None if expired() else batch_rollouts(native, root, seat, group, make_opp(),
                                                                     deadline=deadline, **kw)
        for cid, group in parts:
            vals = results.get(cid)
            if vals is None:
                hit = True
                continue
            L.update(zip(group, vals))
            n_learned += len(group)
    else:
        hit = True
        work = original
    if pool is not None and pool.pending:
        hit = True
    tm['learned'] = time.monotonic() - t0 - tm['native']
    if pool is not None:
        tm.update(pool.timing)
    scores = {}
    for a in work:
        k = WAIT if a == 2400 else a
        b = first.get(k) if k < WAIT else nat.get(k)
        if b is None or k not in L:
            continue
        scores[a] = (b + L[k]) / 2
    elixir = float(core.info.packet.observation.global_features[5])*10
    for a in scores:
        scores[a] = _bonus(a, scores[a], elixir)
    best = _argmax(work, scores)
    core.last = dict(candidates=work, scores=[scores.get(a) for a in work], traces=[])
    core.deadline_stats = dict(hit=hit, fallback=best is None, completed=len(scores), candidates=len(work))
    info = dict(rollouts=n_native + n_learned, native=n_native, learned=n_learned,
                phase_ms={k: round(1e3 * v, 2) for k, v in tm.items()})   # diagnostics only
    if pool is not None:
        info['pool_cpu'] = pool.cpu
    return best, info


class _FastMixin:
    """Installs reduce_fast as core.score_candidates (deadline/fallback honoured)."""

    def _install_fast(self, ctx):
        import sdefault
        if self.fast_prep:
            install_fast_prep(self.rt)
        core = self.p.core
        model = load_model(self.model_name)
        seed = ctx.seed
        pool = get_pool(self.pool_size, core.native, self.model_name) if self.pool_size else None
        threads = self.native_threads

        def make_opp():
            return Learned(model, self.sample, self.switch, self.interval, seed=[seed, int(core.info.tick)],
                           rowwise=self.rowwise)

        def score_candidates(root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
            opp_spec = dict(model=self.model_name, sample=self.sample, switch=self.switch,
                            interval=self.interval, seed=[seed, int(core.info.tick)], rowwise=self.rowwise)
            action, info = reduce_fast(core, root, seat, candidates, make_opp=make_opp, opp_spec=opp_spec,
                                       threads=threads, chunks=self.chunks, pool=pool, deadline=deadline,
                                       coarse_order=core.coarse_order, refine_proposals=core.refine_proposals)
            action = fallback if action is None else action
            core.selected_wait_ticks = TIMED_WAITS.get(action, 0)
            action = sdefault.apply_default(core, action, fallback, candidates)
            core.deadline_stats['rollouts'] = info['rollouts']
            self._dec = info
            return action
        core.score_candidates = score_candidates
        self._dec = {}


class FastLearnedPlayer(_FastMixin, LearnedOppPlayer):
    """Deterministic K4L-R with t/c/p tokens (no deadline)."""

    def __init__(self, rt, *, threads=1, chunks=0, pool=0, fast_prep=False, **kw):
        super().__init__(rt, **kw)
        self.native_threads, self.chunks, self.pool_size, self.fast_prep = threads, chunks, pool, fast_prep

    def start(self, ctx):
        LearnedOppPlayer.start(self, ctx)
        self._install_fast(ctx)


def wall_player_class():
    from bot.live.player import WallCandidatePlayer

    class WallLearnedPlayer(_FastMixin, WallCandidatePlayer):
        """K4L-R under a wall deadline: WallCandidatePlayer's preparation/cutoff handling + reduce_fast."""

        def __init__(self, rt, *, wall_ms, threads, chunks=0, pool=0, model='pool', sample=False, switch=None,
                     interval=5, rowwise=False, fast_prep=False, name=None):
            super().__init__(rt, r3a=16, wall_ms=wall_ms, threads=threads, name=name)
            self.model_name, self.sample, self.switch, self.interval = model, sample, switch, interval
            self.rowwise, self.fast_prep = rowwise, fast_prep
            self.native_threads, self.chunks, self.pool_size = threads, chunks, pool

        def start(self, ctx):
            if self.pool_size:      # fork before the K kernel's thread pool can exist in this process
                get_pool(self.pool_size, self.rt.R.native, self.model_name)
            super().start(ctx)
            self._install_fast(ctx)

        def act(self, view, **kw):
            self._dec = {}
            return super().act(view, **kw)

        def _done(self, action, stats, wall0, wait_ticks=0):
            return super()._done(action, dict(stats, **self._dec), wall0, wait_ticks)
    return WallLearnedPlayer


def make_fast_player(rt, name, arm, kw):
    """Called by lopp.make_lopp_player when a t/c/p/w token is present."""
    if arm['kind'] != 'R':
        raise ValueError(f'{name}: t/c/p/w tokens are defined for kind R only')
    if kw.get('pool') and kw.get('chunks'):
        raise ValueError(f'{name}: use c<P> (serial twin) or p<P> (processes), not both')
    if 'wall_ms' in kw:
        if kw.get('threads', 1) not in (1, 2, 4):
            raise ValueError(f'{name}: w<ms> needs t1, t2 or t4')
        kw.setdefault('threads', 1)
        return wall_player_class()(rt, name=name, **kw)
    return FastLearnedPlayer(rt, arm=arm, name=name, **kw)


def make_live_lopp(rt, name):
    """'LIVE-K4L-R-...-w<ms>-t<N>[-p<P>]': bot.live.player.LivePlayer (it5s2 fast tier and cutoff default) whose
    search tier is this module's wall K4L. Suffix '-dR3a' keeps R3a as the cutoff default."""
    from bot.live.player import LivePlayer, live_belief_class  # noqa: F401  (LivePlayer.start installs it)
    from bot.search.lopp import make_lopp_player
    body, dflt = (name[5:-5], 'R3a') if name.endswith('-dR3a') else (name[5:], 'it5s2')
    search = make_lopp_player(rt, body)
    if search.deadline_seconds is None:
        raise ValueError(f'{name}: the live tier needs w<ms>')
    live = LivePlayer(rt, tier='search', wall_ms=int(1000 * search.deadline_seconds), threads=search.threads,
                      cutoff_default=dflt, name=name)
    live.search = search
    return live
