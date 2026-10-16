"""K4L-R under a wall budget: threaded native rollouts, learned rollouts in persistent worker processes (exploration).

K4L-R-gs (bot/search/lopp.py) spends its decision on ~22 native balanced rollouts (coarse scan + waits) and ~11
Python-driven learned-opponent rollouts (WAIT, timed waits, top-8 plays). Measured with bot/search/lopp_gil.py (1 vs 4
threads, 4 pinned quiet cores, 2026-10-15): the pinned native releases the GIL in rollout_e1 (3.75x),
BattleState.step (3.52x) and NativeScripts.select_action (3.69x), but clone (0.25x), evaluate (0.32x), public_mask
(0.63x), public_view (0.70x) and apply_discrete (0.94x) do not scale, and the opponent's decide step is Python/numpy
on the GIL (json.loads + featurize 1.07x, the one-row forward 0.71x). That decide step is about half of a learned
rollout, so the learned loop does not scale with threads (a learned batch: 142 ms serial, 135 ms on 4 threads, 66 ms
in the 4-process pool). Tokens added to 'K4L-R...' names (kind R only):

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
- fc    fp plus roots built with only the cards the state references in the config (cheaper parse/snapshot/
        shipping): both players' hand and cycle plus every card named anywhere in the players, entities and pending
        casts (config_need), or the whole config when a looked-up key is not a card. Only the snapshot's dynamic
        part (~60 KB) travels per decision; workers hold the config (sent once) and rebuild the root with the same
        cut (ConfigCache; 1.1 vs 7.1 ms to parse).
- w<ms> wall deadline through bot/live/player.py's WallCandidatePlayer (cutoff = start + ms - 8 ms reserve;
        preparation cutoffs as K4CW). At the cutoff only keys with both a balanced and a learned value count;
        if no play is complete the S-default rule plays the cutoff default (R3a, or it5s2 under LIVE-).
        Requires t<N> (sets the K kernel's thread count too).
Round-2 tokens (lopp.py: W<pct>, K<n>, T<n>, m<a>+<b>, b<p|m><tenths>) work here too: each learned sample j is
its own set of chunks (the waits chunk of sample j goes to worker j mod P at the start of the decision); with rw
the values equal the serial arm's. Under w<ms> a key counts only once all K samples are in.
Examples: K4L-R-gs-t4 (== K4L-R-gs), K4L-R-gs-c4 (serial twin), K4L-R-gs-t4-p4, K4L-R-gs-w200-t4-p4,
LIVE-K4L-R-gs-w200-t4-p4 (LivePlayer search tier with this search; it5s2 fast tier and cutoff default).
Without w<ms> nothing reads the clock, so every arm is deterministic.
Failures: a native panic (pyo3 PanicException, a BaseException) in a rollout thread or a pool worker, or a dead pool
worker (EOF/broken pipe), fails the whole decision (lopp.fail_decision: no score, hit, so the cutoff default plays);
counted in lopp.FAILURES. A worker survives a panic; a dead worker's pool is replaced at the next decision.
"""
from __future__ import annotations

import importlib
import multiprocessing as mp
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from multiprocessing.connection import wait as wait_conns

from bot.players.base import WAIT
from bot.search.lopp import (FAILURES, Learned, LearnedOppPlayer, batch_rollouts, fail_decision, fatal, load_model,
                              mean_samples, mix, note_failure, sample_seed)
from bot.search.oppmodel import STYLES, TIMED_WAITS, _argmax, _bonus
from bot.search.reserve import apply as reserve_apply

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


def _card_names(obj, cards, out):
    """Every string (value or key) anywhere in obj that is a card name -> out."""
    if isinstance(obj, str):
        if obj in cards:
            out.add(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in cards:
                out.add(k)
            if not isinstance(v, (int, float, bool)) and v is not None:
                _card_names(v, cards, out)
    elif isinstance(obj, list):
        for v in obj:
            if not isinstance(v, (int, float, bool)) and v is not None:
                _card_names(v, cards, out)


def config_need(players, entities, pending, cards):
    """The cards an fc root keeps: both players' hand and cycle, and every card named anywhere in the entities
    (stats name/payload key, chain sources, spawn and building templates, spell areas) and pending casts. Extra
    cards cannot change a rollout (the native only looks cards up by name). None (= keep the whole config) when a
    key the native indexes without a fallback is not a card at all: a hand/cycle card, a pending cast, an area's
    spell, or the stats key of a chain source (electro_land: config.cards[key].chain)."""
    looked_up = {c for p in players for c in p['hand'] + p['cycle']}
    looked_up.update(c['name'] for c in pending if isinstance(c, dict) and c.get('name'))
    for e in entities:
        st = e.get('stats') or {}
        if e.get('spell_name'):
            looked_up.add(e['spell_name'])
        if st.get('chain_count') or st.get('dragon_chain'):
            looked_up.add(st.get('payload_key') or st.get('name'))
    if not looked_up <= cards.keys():
        return None
    need = set(looked_up)
    _card_names(entities, cards, need)
    _card_names(pending, cards, need)
    return tuple(sorted(need))


class ConfigCache:
    """Rebuilds a root from (head, tail) and a cached config, keeping only the cards the state references
    (config_need; the whole config if it returns None). The cut config is re-serialized by Python's json (shortest
    round-trip floats; the native parses with float_roundtrip), so the values are exact; lopp_fast_check
    verifies every rollout value on such roots against the original root."""

    def __init__(self, text):
        import json
        cfg = json.loads(text)
        self.full = text
        self.other = json.dumps({k: v for k, v in cfg.items() if k != 'cards'})[1:-1]
        self.cards = {n: json.dumps(n) + ':' + json.dumps(v) for n, v in cfg['cards'].items()}
        self.cut = {}

    def need(self, head, tail):
        """config_need on a snapshot's dynamic part (serde field order: players, entities, ... config,
        pending_casts); None if the layout is not found."""
        import json
        dec = json.JSONDecoder()
        try:
            players = dec.raw_decode(head, head.index('"players":') + 10)[0]
            entities = dec.raw_decode(head, head.index('"entities":') + 11)[0]
            pending = dec.raw_decode(tail, tail.index('"pending_casts":') + 16)[0]
        except ValueError:
            return None
        return config_need(players, entities, pending, self.cards)

    def payload(self, head, tail):
        need = self.need(head, tail)
        if need is None:
            return head + self.full + tail
        if need not in self.cut:
            self.cut[need] = '{' + self.other + ',"cards":{' + ','.join(self.cards[n] for n in need) + '}}'
        return head + self.cut[need] + tail


def opponent_from_spec(opp, j=0):
    """Learned sample j from the pool's opponent spec (models list, CRN key seed + [j] for j > 0)."""
    models = opp.get('models') or [opp['model']]
    m, key = load_model(models[j % len(models)]), sample_seed(opp['seed'], j + opp.get('offset', 0))
    own = (Learned(m, opp['sample'], None, opp['interval'], seed=[*key, 7777], rowwise=opp.get('rowwise', False),
                   bias=opp.get('bias', 0.)) if opp.get('own') else None)
    return Learned(m, opp['sample'], opp['switch'], opp['interval'], seed=key, rowwise=opp.get('rowwise', False),
                   bias=opp.get('bias', 0.), own=own)


def _pool_worker(conn, native, spawn=None):
    """Worker loop: ('root', gen, snapshot, seat, kw, opp, cutoff) then ('run', gen, cid, keys[, sample]) ->
    ('done', ...).
    spawn = (native module name, metadata JSON, model names): a spawned worker builds its own NativeScripts."""
    if spawn is not None:
        module, meta, models = spawn
        native = importlib.import_module(module).NativeScripts(meta)
        for name in models:
            load_model(name)
    state_class = importlib.import_module(type(native).__module__).BattleState
    root = seat = kw = opp = cutoff = configs = root_err = None
    keyed = {}                                  # content-hash keyed configs (LearnedPool.begin), FIFO as the parent
    gen, t_parse = -1, 0.
    while True:
        try:
            msg = conn.recv()
        except EOFError:
            return
        if msg[0] == 'config':
            if len(msg) > 2:                    # (text, key, raw): raw = an fc root's own cut config, used as is
                keyed[msg[2]] = msg[1] if msg[3] else ConfigCache(msg[1])
                while len(keyed) > CONFIG_CACHE:
                    keyed.pop(next(iter(keyed)))
            else:
                configs = ConfigCache(msg[1])
        elif msg[0] == 'root':
            _, gen, snap, seat, kw, opp, cutoff = msg
            t0 = time.monotonic()
            try:
                if isinstance(snap, str):
                    payload = snap
                elif len(snap) > 2:
                    c = keyed[snap[2]]
                    payload = snap[0] + c + snap[1] if isinstance(c, str) else c.payload(snap[0], snap[1])
                else:
                    payload = configs.payload(*snap)
                root, root_err = state_class(payload), None
            except BaseException as ex:
                if fatal(ex):
                    raise
                root, root_err = None, f'root: {ex!r:.300}'
            t_parse = time.monotonic() - t0
        elif msg[0] == 'run':
            _, g, cid, keys = msg[:4]
            j = msg[4] if len(msg) > 4 else 0
            c0, w0 = time.process_time(), time.monotonic()
            vals = err = None
            if g == gen and root_err is not None:
                err = root_err
            elif g == gen and (cutoff is None or time.monotonic() < cutoff):
                try:
                    # a style name: exactness checks
                    opponent = opp if isinstance(opp, str) else opponent_from_spec(opp, j)
                    vals = batch_rollouts(native, root, seat, keys, opponent, deadline=cutoff, **kw)
                except BaseException as ex:     # a native panic: report it, keep serving (root is untouched)
                    if fatal(ex):
                        raise
                    vals, err = None, repr(ex)[:300]
            conn.send(('done', g, cid, vals, time.process_time() - c0, time.monotonic() - w0, t_parse, err))
        else:
            return


CONFIG_CACHE = 16     # configs a pool worker keeps (keyed by content hash, FIFO, mirrored by LearnedPool.shipped)


class LearnedPool:
    """P worker processes holding the native scripts and the opponent nets. Start method: fork (Linux default;
    the nets are loaded before the fork) or spawn (macOS default, where fork after torch/Accelerate is unsafe;
    the worker rebuilds NativeScripts from `meta`, the JSON the planner's own NativeScripts was built from).
    CLASHER_LOPP_POOL_START overrides."""

    def __init__(self, n, native, model_names=(), meta=None, config=None):
        import os
        import sys
        method = os.environ.get('CLASHER_LOPP_POOL_START', 'spawn' if sys.platform == 'darwin' else 'fork')
        for name in model_names:
            load_model(name)
        ctx = mp.get_context(method)
        spawn = None
        if method != 'fork':
            if meta is None:
                raise ValueError('a spawned pool needs the native metadata JSON')
            spawn = (type(native).__module__, meta, tuple(model_names))
        self.method = method
        self.conns, self.procs = [], []
        for _ in range(n):
            here, there = ctx.Pipe()
            proc = ctx.Process(target=_pool_worker, args=(there, None if spawn else native, spawn), daemon=True)
            proc.start()
            there.close()
            self.conns.append(here)
            self.procs.append(proc)
        self.gen = 0
        self.pending, self.results, self.cpu = {}, {}, 0.
        self.timing = {}
        self.config = None
        self.base_config = config        # R.config: legacy protocol only (base_cut=None): fc roots travel as their dynamic part
        self.base_sent = False
        self.shipped = {}                # content hashes of the configs the workers hold (FIFO, CONFIG_CACHE)
        self.broken = False              # a worker died (EOF / broken pipe): get_pool replaces the pool
        self.errors = []                 # worker-reported failures (native panics) of the current decision

    def begin(self, root, seat, kw, opp, cutoff, base_cut=None):
        """Raises OSError/EOFError (and sets broken) when a worker is gone.
        base_cut (reduce_fast passes the player's fc flag): every root's static part, its config text, ships once per
        worker keyed by its content hash, so a config reaches the workers once whatever its size and is never stale.
        An fc root's config is already cut, and the workers use it as is (raw); others are cut per root (ConfigCache).
        base_cut=None: the legacy protocol, unchanged (bot/noise/mr_fast.MRPool and its worker rely on it)."""
        self.gen += 1
        self.pending, self.results, self.cpu, self.errors = {}, {}, 0., []
        self.timing = dict(parse=0., chunk=0.)
        snap = root.snapshot()
        parts = split_snapshot(snap)
        if base_cut is not None:
            if parts is None:
                msg = snap
            else:
                import hashlib
                raw = bool(base_cut)
                key = hashlib.sha1(parts[1].encode()).hexdigest() + ('r' if raw else 'c')
                if key not in self.shipped:
                    self._send_all(('config', parts[1], key, raw))
                    self.shipped[key] = True
                    while len(self.shipped) > CONFIG_CACHE:
                        self.shipped.pop(next(iter(self.shipped)))
                msg = (parts[0], parts[2], key)
        else:
            if parts is not None and len(parts[1]) < 1 << 20:     # a deck-card config (fc root)
                if self.base_config is None:
                    parts = None                                    # no full config to cut from: ship it whole
                elif not self.base_sent:                            # the workers cut from R.config, sent once
                    import json
                    self.config, self.base_sent = json.dumps(self.base_config), True
                    self._send_all(('config', self.config))
            elif parts is not None and parts[1] != self.config:    # new config (first root, level scaling): once
                self.config = parts[1]
                self._send_all(('config', self.config))
            msg = snap if parts is None else (parts[0], parts[2])
        self._send_all(('root', self.gen, msg, seat, kw, opp, cutoff))

    def _send_all(self, msg):
        for conn in self.conns:
            self._send(conn, msg)

    def _send(self, conn, msg):
        try:
            conn.send(msg)
        except (OSError, EOFError):
            self.broken = True
            raise

    def submit(self, worker, cid, keys, sample=0):
        self._send(self.conns[worker], ('run', self.gen, cid, list(keys)) + ((sample,) if sample else ()))
        self.pending[cid] = worker

    def collect(self, cutoff=None):
        """Wait for every pending chunk (or the cutoff); returns {cid: values or None}."""
        while self.pending:
            remaining = None if cutoff is None else cutoff - time.monotonic()
            if remaining is not None and remaining <= 0:
                break
            busy = [self.conns[w] for w in set(self.pending.values())]
            for conn in wait_conns(busy, timeout=remaining):
                try:
                    _, gen, cid, vals, cpu, wall, parse, err = conn.recv()
                except (OSError, EOFError):       # the worker died (killed, segfault): stop waiting for it
                    self.broken = True
                    w = self.conns.index(conn)
                    lost = [c for c, x in self.pending.items() if x == w]
                    for c in lost:
                        self.pending.pop(c)
                    self.errors.append(f'worker {w} died ({len(lost)} chunks lost)')
                    continue
                if gen != self.gen:
                    continue                      # a chunk abandoned at an earlier decision's cutoff
                if err is not None:
                    self.errors.append(err)
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
            if proc.is_alive():           # busy on an abandoned chunk (broken pool): do not wait for it
                proc.kill()
                proc.join(timeout=1)
        for conn in self.conns:
            conn.close()


class _ConfigJson:
    """Stands in for `json` in fair_player / bot.live.levels: dumps(dict(..., config=R.config)) with config as the
    last key returns json.dumps(rest)[:-1] + ', "config": ' + <cached json.dumps(R.config)> + '}', byte for byte
    what json.dumps would return (default separators), without re-serializing the 2 MB catalogue each root."""

    def __init__(self, config, verify):
        import json
        self._json, self._config, self._verify = json, config, verify
        self._text = json.dumps(config)
        self.hits = 0
        self.cut, self._cut = False, {}

    def __getattr__(self, name):
        return getattr(self._json, name)

    def dumps(self, obj, *args, **kw):
        if args or kw or type(obj) is not dict or obj.get('config') is not self._config or list(obj)[-1] != 'config':
            return self._json.dumps(obj, *args, **kw)
        rest = self._json.dumps({k: v for k, v in obj.items() if k != 'config'})
        cfg = self._text
        need = (config_need(obj['players'], obj.get('entities', ()), obj.get('pending_casts', ()),
                            self._config['cards']) if self.cut else None)
        if need is not None:  # fc: only the cards the state references (as ConfigCache); None: the whole config
            cards = self._config['cards']
            if need not in self._cut:
                self._cut[need] = self._json.dumps(dict(self._config, cards={k: v for k, v in cards.items()
                                                                              if k in need}))
            cfg = self._cut[need]
        text = (rest[:-1] + ', ' if len(rest) > 2 else '{') + '"config": ' + cfg + '}'
        if self._verify and not self.cut and text != self._json.dumps(obj):
            raise AssertionError('fast-prep json differs')
        self.hits += 1
        return text


def install_fast_prep(rt, cut=False):
    """Token fp: output-identical preparation caches, process-wide and idempotent.
    1. Resources.root (and bot.live.levels.LevelRoot) json.dumps of the config -> _ConfigJson.
    2. proposals.outputs memo: K4C-r16's candidate list re-runs R3a's forward (bot/search/candidates.py ranked,
       r3a=16 > the poller's cached 8) on the same features the poller just used; an identical feature batch
       (every tensor torch.equal, same model) returns the previous outputs.
    CLASHER_FASTPREP_VERIFY=1 recomputes both the slow way and raises on any difference.
    cut=True (token fc; switches on for the whole process, never off): roots are built with only the referenced
    cards (config_need) in the config, as the pool workers' ConfigCache does (7 -> ~1.5 ms to parse, 5 -> ~1 ms
    to snapshot); not byte-identical, but every rollout value equal (lopp_fast_check) and command hashes equal end
    to end."""
    import os
    import sys
    if getattr(rt, '_fast_prep', False):
        rt._fast_prep_shim.cut |= cut
        return
    verify = os.environ.get('CLASHER_FASTPREP_VERIFY') == '1'
    shim = _ConfigJson(rt.R.config, verify)
    shim.cut = cut
    rt._fast_prep_shim = shim
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


def get_pool(n, native, model_name, meta=None, config=None):
    """One pool per process (started once, before any thread pool exists in this process).
    meta: R.meta (dict) or its JSON; only a spawned pool uses it. model_name may be 'a+b' (all loaded).
    A broken pool (a worker died) is closed and replaced here, at the start of the next decision. With fork that
    forks after this process's threads exist (idle between decisions); only a hard worker death gets here, since a
    worker survives native panics."""
    import json
    if n in _POOLS and (_POOLS[n].broken or not all(proc.is_alive() for proc in _POOLS[n].procs)):
        _POOLS.pop(n).close()
        FAILURES['pool_recreated'] += 1
    if n not in _POOLS:
        if meta is not None and not isinstance(meta, str):
            meta = json.dumps(meta)
        _POOLS[n] = LearnedPool(n, native, tuple(model_name.split('+')), meta, config)
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
                deadline=None, coarse_order=(), refine_proposals=(), lw=None, samples=1, top=8, base_cut=None):
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
    failed = []               # native panics / dead workers: the decision is given up (cutoff default)
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
        except BaseException as ex:   # a native panic (PanicException is a BaseException)
            if fatal(ex):
                raise
            failed.append(('native_thread', ex))
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
        try:
            # Legacy pools (bot/noise/mr_fast.MRPool) take no base_cut: pass it only when cutting.
            pool.begin(root, seat, kw, opp_spec, deadline, **({} if base_cut is None else {'base_cut': base_cut}))
            for j in range(samples):
                pool.submit(j % len(pool.conns), ('w', j), waits, j)
        except (OSError, EOFError) as ex:
            failed.append(('pool_dead', ex))
        tm['ship'] = time.monotonic() - t0
    if threads == 1:
        for a in todo:
            v = rollout(a)
            if v is None or failed:
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
    if failed:
        work = original
    elif all(a in nat for a in scan):
        first = {a: 0. + nat[a] for a in scan}
        chosen = set(sorted(plays, key=lambda a: (-first[a], original.index(a)))[:top])
        chosen.update(a for a in refine_proposals if a in plays)
        work = [a for a in original if a >= WAIT or a in chosen]
        keys = [a for a in original if (a >= WAIT and a != 2400) or a in chosen]
        if pool is not None:
            P = len(pool.conns)
            parts = [((cid, j), group) for j in range(samples) for cid, group in chunk_keys(keys, P)]
            try:
                for (cid, j), group in parts:
                    if cid != 'w':
                        pool.submit((cid + j) % P, (cid, j), group, j)   # sample j's plays shifted by j workers
                results = pool.collect(deadline)
            except (OSError, EOFError) as ex:
                failed.append(('pool_dead', ex))
                results = {}
            if pool.errors:
                failed.append(('pool_dead' if pool.broken else 'native_pool', pool.errors[0]))
        else:
            base = chunk_keys(keys, chunks) if chunks else [('all', list(dict.fromkeys(keys)))]
            parts = [((cid, j), group) for j in range(samples) for cid, group in base]
            results = {}
            for (cid, j), group in parts:
                try:
                    results[cid, j] = None if expired() else batch_rollouts(native, root, seat, group, make_opp(j),
                                                                            deadline=deadline, **kw)
                except BaseException as ex:
                    if fatal(ex):
                        raise
                    failed.append(('native_serial', ex))
                    break
        per = {}
        for cid, group in parts:
            vals = results.get(cid)
            if vals is None:
                hit = True
                continue
            for a, v in zip(group, vals):
                per.setdefault(a, {})[cid[1]] = v
            n_learned += len(group)
        L = {a: mean_samples([d[j] for j in range(samples)]) for a, d in per.items() if len(d) == samples}
    else:
        hit = True
        work = original
    if pool is not None and pool.pending:
        hit = True
    tm['learned'] = time.monotonic() - t0 - tm['native']
    if pool is not None:
        tm.update(pool.timing)
    if failed:
        kind, ex = failed[0]
        note_failure(kind, ex)
        fail_decision(core, work, kind)
        info = dict(rollouts=n_native + n_learned, native=n_native, learned=n_learned, native_failure=kind,
                    phase_ms={k: round(1e3 * v, 2) for k, v in tm.items()})
        return None, info
    scores = {}
    for a in work:
        k = WAIT if a == 2400 else a
        b = first.get(k) if k < WAIT else nat.get(k)
        if b is None or k not in L:
            continue
        scores[a] = mix(b, L[k], lw)
    elixir = float(core.info.packet.observation.global_features[5])*10
    for a in scores:
        scores[a] = _bonus(a, scores[a], elixir)
    reserve_apply(core, scores, elixir)              # token res only (bot/search/reserve.py)
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
        if self.fast_prep or self.fast_cut:
            install_fast_prep(self.rt, cut=self.fast_cut)
        core = self.p.core
        if self.arm.get('reserve'):
            from bot.search.reserve import install
            install(self.rt, core, ctx.own_order)
        if self.arm.get('leafcorr') is not None:
            from bot.search.reserve import install_leafcorr
            install_leafcorr(self.rt, core, ctx.own_order, self.arm['leafcorr'])
        names = self.model_name.split('+')
        for name in names:
            load_model(name)
        seed = ctx.seed

        def current_pool():     # the process pool; a broken one is replaced here (next decision)
            return (get_pool(self.pool_size, core.native, self.model_name, getattr(self.rt.R, 'meta', None),
                             self.rt.R.config) if self.pool_size else None)
        current_pool()
        threads = self.native_threads
        arm = self.arm

        def spec():
            return dict(model=names[0], models=names, sample=self.sample, switch=self.switch,
                        interval=self.interval, seed=[seed, int(core.info.tick)], rowwise=self.rowwise,
                        bias=self.bias, own=bool(arm.get('own')), offset=arm.get('offset', 0))

        def make_opp(j=0):
            return opponent_from_spec(spec(), j)

        def score_candidates(root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
            action, info = reduce_fast(core, root, seat, candidates, make_opp=make_opp, opp_spec=spec(),
                                       threads=threads, chunks=self.chunks, pool=current_pool(), deadline=deadline,
                                       coarse_order=core.coarse_order, refine_proposals=core.refine_proposals,
                                       lw=arm.get('lw'), samples=arm.get('samples', 1), top=arm.get('top', 8),
                                       base_cut=self.fast_cut)
            action = fallback if action is None else action
            core.selected_wait_ticks = 0 if arm.get('rh') else TIMED_WAITS.get(action, 0)
            action = sdefault.apply_default(core, action, fallback, candidates)
            core.deadline_stats['rollouts'] = info['rollouts']
            self._dec = info
            return action
        core.score_candidates = score_candidates
        self._dec = {}


class FastLearnedPlayer(_FastMixin, LearnedOppPlayer):
    """Deterministic K4L-R with t/c/p tokens (no deadline)."""

    def __init__(self, rt, *, threads=1, chunks=0, pool=0, fast_prep=False, fast_cut=False, **kw):
        super().__init__(rt, **kw)
        self.native_threads, self.chunks, self.pool_size, self.fast_prep = threads, chunks, pool, fast_prep
        self.fast_cut = fast_cut

    def start(self, ctx):
        LearnedOppPlayer.start(self, ctx)
        self._install_fast(ctx)


def wall_player_class():
    from bot.live.player import WallCandidatePlayer

    class WallLearnedPlayer(_FastMixin, WallCandidatePlayer):
        """K4L-R under a wall deadline: WallCandidatePlayer's preparation/cutoff handling + reduce_fast."""

        def __init__(self, rt, *, wall_ms, threads, chunks=0, pool=0, model='pool', sample=False, switch=None,
                     interval=5, rowwise=False, fast_prep=False, fast_cut=False, bias=0., arm=None, name=None):
            super().__init__(rt, r3a=16, wall_ms=wall_ms, threads=threads, name=name)
            self.model_name, self.sample, self.switch, self.interval = model, sample, switch, interval
            self.bias, self.arm = bias, arm or dict(kind='R')
            self.rowwise, self.fast_prep, self.fast_cut = rowwise, fast_prep, fast_cut
            self.native_threads, self.chunks, self.pool_size = threads, chunks, pool

        def start(self, ctx):
            if self.pool_size:      # fork before the K kernel's thread pool can exist in this process
                get_pool(self.pool_size, self.rt.R.native, self.model_name, getattr(self.rt.R, 'meta', None),
                         self.rt.R.config)
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
        return wall_player_class()(rt, name=name, arm=arm, **kw)
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
