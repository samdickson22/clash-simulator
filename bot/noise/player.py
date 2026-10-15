"""Noise-robust decision wrappers (bot lead, exploration). Names (resolved by bot/noise/run.py's make_player):

  'NR-<filter tag>:<player>'   <player> decides from the packet rewritten by bot/noise/filter.py EntityFilter.
                               Scope 'a' (default): every tier (it5s2 fast tier, R3a/it5s2 proposals, search root)
                               sees the filtered view. Scope 'r': only the search root (LivePlayer's search tier
                               root_fn); the fast tier and the candidate list see the raw view.
  'CAP:<player>'               outermost wrapper (outside PERC-*): hands the TRUE view to every NR filter in this
                               process so it can score raw vs filtered entity tables against the truth (fidelity
                               diagnostics only; the decision never reads it).

Fair information: the filter reads only the packets the bot itself received (its own observation history).
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import replace

import numpy as np

from bot.noise.filter import EntityFilter, parse_config, with_entities, _entities, TOWER_NAMES, BOARD_W, BOARD_H

TRUTH = {'view': None}


def tower_ids(rt):
    names = rt.R.builder.token_names
    return [i for i, n in enumerate(names) if n in TOWER_NAMES]


class NoiseRobustPlayer:
    def __init__(self, rt, tag, inner):
        self.rt, self.cfg, self.inner = rt, parse_config(tag), inner
        self.name = f'NR-{tag}:{inner.name}'
        self.deadline_seconds = inner.deadline_seconds
        self.towers = tower_ids(rt)
        self.fid = Counter()

    @property
    def decisions(self):
        return getattr(self.inner, 'decisions', [])

    def start(self, ctx):
        # PercPlayer restarts the inner player after a cycle-tracker resync (history rewrite) several times per
        # match; the entity tracks stay valid, so the filter (and the capture) persist within the same match.
        import os
        same = getattr(self, 'ctx', None) is not None and (self.ctx.seed, self.ctx.seat) == (ctx.seed, ctx.seat)
        if not same:
            self.filter = EntityFilter(self.cfg, self.towers)
            self.dump = [] if os.environ.get('NR_DUMP') else None
            self.fid = Counter()
        else:
            self.fid['restarts'] += 1
        self.ctx = ctx
        self.inner.start(ctx)
        self._root_fn_installed = False
        if self.cfg.scope == 'r':
            search = getattr(self.inner, 'search', None)
            if search is None:
                raise ValueError(f'{self.name}: scope r needs a LivePlayer search tier')
            base = search.root_fn or self.rt.R.root
            nr = self

            def root_fn(info, opponent, rng):
                return base(replace(info, packet=nr._filtered), opponent, rng)
            search.root_fn = root_fn

    def act(self, view):
        plays = ()
        if self.cfg.ev:     # D1 rows: absolute seats and tiles; the packet is in the acting seat's frame
            rot = view.seat == 1
            plays = [(e['seat'] == view.seat, 18 - e['x'] if rot else e['x'], 32 - e['y'] if rot else e['y'], e['tick'])
                     for e in view.public_events[-16:] if e.get('kind') == 'card' and view.tick - e['tick'] <= self.cfg.ev]
        packet = self.filter.update(view.tick, view.info.packet, plays)
        if TRUTH['view'] is not None:
            self._fidelity(TRUTH['view'], view.info.packet, packet)
            if self.dump is not None:
                self.dump.append((view.tick, _entities(TRUTH['view'].info.packet), _entities(view.info.packet)))
        if packet is view.info.packet:
            return self.inner.act(view)
        if self.cfg.scope == 'r':
            self._filtered = packet
            return self.inner.act(view)
        info = replace(view.info, packet=packet)
        if view.reserved is view.info:
            reserved = info
        else:
            reserved = replace(view.reserved, packet=with_entities(view.reserved.packet, _entities(packet)))
        return self.inner.act(type(view)(view.tick, view.seat, info, reserved, view.public_events, view.pending,
                                         view.can_act))

    def _fidelity(self, true_view, raw, filt):
        towers = set(self.towers)

        def units(p):
            return [(e[0], e[1][2] > .5, float(e[1][0])*BOARD_W, float(e[1][1])*BOARD_H) for e in _entities(p)
                    if e[0] not in towers and int(np.argmax(e[1][4:9])) <= 1]
        T = units(true_view.info.packet)
        for tag, p in (('raw', raw), ('flt', filt)):
            P = units(p)
            cand = sorted((math.hypot(a[2]-b[2], a[3]-b[3]), i, j) for i, a in enumerate(P) for j, b in enumerate(T)
                          if a[1] == b[1])
            ui, uj, same = set(), set(), 0
            for d, i, j in cand:
                if d > 1.0:
                    break
                if i in ui or j in uj:
                    continue
                ui.add(i); uj.add(j); same += P[i][0] == T[j][0]
            self.fid[f'{tag}_true'] += len(T)
            self.fid[f'{tag}_pred'] += len(P)
            self.fid[f'{tag}_match'] += len(uj)
            self.fid[f'{tag}_same_body'] += same
            for i, a in enumerate(P):
                if i not in ui:
                    self.fid[f'{tag}_phantom_{"own" if a[1] else "opp"}'] += 1
            for j, b in enumerate(T):
                if j not in uj:
                    self.fid[f'{tag}_missed_{"own" if b[1] else "opp"}'] += 1

    def summary(self):
        out = {f'nr_{k}': v for k, v in self.filter.stats.items()}
        out.update({f'fid_{k}': v for k, v in self.fid.items()})
        return out

    def close(self):
        if self.dump:
            import os
            import pickle
            path = os.path.join(os.environ['NR_DUMP'], f'{self.ctx.seed}-{self.ctx.seat}-{os.getpid()}.pkl')
            with open(path, 'wb') as fh:
                pickle.dump(dict(seed=self.ctx.seed, seat=self.ctx.seat, polls=self.dump), fh, protocol=4)
            self.dump = None
        self.ctx = None
        self.inner.close()


class CapturePlayer:
    def __init__(self, inner):
        self.inner, self.name = inner, f'CAP:{inner.name}'
        self.deadline_seconds = inner.deadline_seconds

    def start(self, ctx):
        self.inner.start(ctx)

    def act(self, view):
        TRUTH['view'] = view
        try:
            return self.inner.act(view)
        finally:
            TRUTH['view'] = None

    def close(self):
        self.inner.close()


def find(player, cls):
    """The first wrapper of class `cls` in a PERC/NR/CAP chain (or None)."""
    seen = 0
    while player is not None and seen < 8:
        if isinstance(player, cls):
            return player
        player = getattr(player, 'inner', None)
        seen += 1
    return None


def make_det_live_lopp(rt, name):
    """'LIVED-K4L-<lopp body>': the deterministic twin of LIVE-K4L-<body>-w<ms>-t4-p4 (bot/search/lopp_fast.py
    make_live_lopp): the same LivePlayer (it5s2 fast tier as the default and proposer) and the same K4L search, but
    no wall deadline, one thread, no process pool. Every search completes, so the arm is load-insensitive and
    reproducible (screens on loaded hosts); the live arm's cutoff-default share (~2%) is the only difference."""
    from bot.live.player import LivePlayer
    from bot.search.lopp import make_lopp_player
    body = name[6:]
    search = make_lopp_player(rt, body + '-w200-t1')
    search.set_deadline(None, 1)
    live = LivePlayer(rt, tier='search', wall_ms=200, threads=1, cutoff_default='it5s2', name=name)
    live.search, live.deadline_seconds = search, None
    return live


def make_reseeded_perc(rt, name, fallback):
    """'PERCs<k>-<arm>:<player>': bot/live/perc.py PercPlayer, unchanged, with its noise stream seeded
    [seed, seat, 0x9e4c, k] instead of [seed, seat, 0x9e4c] (reseeded reference runs; same noise model)."""
    import re
    from bot.live.perc import PercPlayer
    m = re.fullmatch(r'PERCs(\d+)-([^:]+):(.+)', name)
    k, arm, inner = int(m[1]), m[2], m[3]

    class Reseeded(PercPlayer):
        def start(self, ctx):
            super().start(ctx)
            self.rng = np.random.default_rng([ctx.seed, ctx.seat, 0x9e4c, k])
            if self.noise is None:
                from bot.live.empirical import EmpiricalNoise
                self.channel = EmpiricalNoise(self.stats, self.rng, list(ctx.own_order))
    p = Reseeded(rt, arm, fallback(rt, inner))
    p.name = name
    return p


def make_player(rt, name, fallback):
    if name.startswith('LIVE-MRK'):
        from bot.noise.mr_fast import make_live_mr
        return make_live_mr(rt, name)
    if name.startswith('LIVEMR-'):
        from bot.noise.multiroot import make_mr_live
        return make_mr_live(rt, name)
    if name.startswith('FAN['):
        from bot.noise.shadow import make_fan
        return make_fan(rt, name, fallback)
    if name.startswith('PERCs'):
        return make_reseeded_perc(rt, name, fallback)
    if name.startswith('LIVED-K4L-'):
        return make_det_live_lopp(rt, name)
    if name.startswith('CAP:'):
        return CapturePlayer(fallback(rt, name[4:]))
    if name.startswith('NR-'):
        tag, _, inner = name[3:].partition(':')
        return NoiseRobustPlayer(rt, tag, fallback(rt, inner))
    return None
