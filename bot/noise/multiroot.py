"""Perception-aware determinization for K4L (lever (b); bot lead, exploration).

    'LIVEMR-K<n>[-D][-U<m>q<pct>]'   LivePlayer (it5s2 fast tier as default and proposer) + serial, deterministic
                                     (no deadline) K4L-R-gs-rw search whose n learned samples are averaged; sample
                                     j > 0 runs from its OWN root:
        D          an independent belief sample of the opponent's hidden hand/cycle (as lopp token D);
        U<m>q<pct> a unit hypothesis: the raw perceived units plus each recently missed unit (a confirmed track
                   undetected for <= m polls, at its last position; bot/noise/filter.py) with probability pct/100.
    Sample 0, the native coarse scan and the candidate list are exactly the baseline's (raw view, belief sample 0).
    'LIVEMR-K1' is the baseline of this code path (lopp.reduce_learned, serial; = K4L-R-gs-rw without the pool).
Fair information: the roots use the bot's own perceived history (tracks) and its belief; the noise model is never
read here (q is a fixed design constant).
"""
from __future__ import annotations

import re
from dataclasses import replace

import numpy as np

from bot.players.base import WAIT


def parse(name):
    m = re.fullmatch(r'LIVEMR-K(\d+)((?:-D)?)(?:-U(\d+)q(\d+))?', name)
    if not m:
        raise ValueError(f'bad multi-root name {name!r}')
    return dict(K=int(m[1]), D=bool(m[2]), Um=int(m[3]) if m[3] else 0, Uq=int(m[4])/100 if m[4] else 0.)


def make_mr_live(rt, name):
    import sdefault
    from bot.live.player import LivePlayer
    from bot.search.lopp import Learned, load_model, sample_seed, reduce_learned, note_failure, fail_decision, fatal
    from bot.search.lopp_fast import wall_player_class
    from bot.search.oppmodel import TIMED_WAITS
    from bot.noise.filter import EntityFilter, FilterConfig, _entities, with_entities
    from bot.noise.player import tower_ids
    spec = parse(name)
    WL = wall_player_class()
    towers = tower_ids(rt)

    class MultiRoot(WL):
        def start(self, ctx):
            super().start(ctx)
            self.trk = EntityFilter(FilterConfig(conf=1, coast=spec['Um'], damp=0.), towers) if spec['Um'] else None
            self._extra = []
            core = self.p.core
            models = [load_model(m) for m in self.model_name.split('+')]
            seed = ctx.seed
            R = self.rt.R
            mr = self

            def root0(info, opponent, rng):
                mr._opp0 = opponent
                return R.root(info, opponent, rng)
            self.root_fn = root0

            def make_opp(j=0):
                key = sample_seed([seed, int(core.info.tick)], j)
                return Learned(models[j % len(models)], self.sample, self.switch, self.interval, seed=key,
                               rowwise=self.rowwise, bias=self.bias, own=None)

            def root_for(j):
                rng = np.random.default_rng([seed, int(core.info.tick), j, 0xD])
                opponent = self.p.belief.sample(rng) if spec['D'] else mr._opp0
                info = core.info
                if spec['Um'] and mr._extra:
                    add = [e for e in mr._extra if rng.random() < spec['Uq']]
                    if add:
                        info = replace(info, packet=with_entities(info.packet, _entities(info.packet) + add))
                return R.root(info, opponent, rng)

            def score_candidates(root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
                try:
                    action, info = reduce_learned(core, root, seat, candidates, self.arm,
                                                  coarse_order=core.coarse_order,
                                                  refine_proposals=core.refine_proposals, make_opp=make_opp,
                                                  root_for=root_for if (spec['D'] or spec['Um']) else None)
                except BaseException as ex:
                    if fatal(ex):
                        raise
                    note_failure('serial', ex)
                    fail_decision(core, candidates, 'serial')
                    action, info = None, dict(rollouts=0, native=0, learned=0, native_failure='serial')
                action = fallback if action is None else action
                core.selected_wait_ticks = TIMED_WAITS.get(action, 0)
                action = sdefault.apply_default(core, action, fallback, candidates)
                core.deadline_stats['rollouts'] = info['rollouts']
                self._dec = info
                return action
            core.score_candidates = score_candidates

        def act(self, view, **kw):
            if self.trk is not None:
                # tracks over every poll; the extra hypothesis units = confirmed tracks missed on this poll (for
                # at most Um polls), at their last detected row
                self.trk.step(view.tick, _entities(view.info.packet))
                self._extra = [t.rows[t.cur] for t in self.trk.tracks if t.confirmed and t.miss > 0]
            return super().act(view, **kw)

    search = MultiRoot(rt, wall_ms=200, threads=1, model='pool', sample=True, rowwise=True,
                       arm=dict(kind='R', samples=spec['K']), name=name + ':search')
    search.set_deadline(None, 1)
    live = LivePlayer(rt, tier='search', wall_ms=200, threads=1, cutoff_default='it5s2', name=name)
    live.search, live.deadline_seconds = search, None
    return live
