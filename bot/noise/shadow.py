"""Decision-quality proxy for noise-robust variants: regret against a true-sight search (bot lead, exploration).

    'CAP:PERC-emp:FAN[<tag>|<tag>|...]:LIVED-K4L-R-gs-rw-fc'

FAN plays the game with the first chain (the unmodified <player> on the noisy view). Every other chain is a shadow:
NR-<tag>:<player> fed the same noisy views; its decisions are recorded, never executed. A TRUTH chain (<player> on
the true view, from CAP) runs alongside. At every decision where the truth chain's search completed, each chain's
action a is scored with the truth search's root scores (core.last: WAIT, timed waits and the top-8 plays):
  regret = max(truth scores) - truth score(a)   (a outside the truth work set: counted as `outside`, no regret)
  agree  = a == truth action
Lower mean regret and higher agreement = decisions closer to what perfect sight would have done, on the same states.
The states visited are the baseline's, so this ranks variants by single-decision quality, not by win rate.
"""
from __future__ import annotations

from collections import Counter

from bot.players.base import WAIT


class FanPlayer:
    def __init__(self, rt, tags, make, inner_name):
        from bot.noise.player import NoiseRobustPlayer
        self.chains = [('base', make(rt, inner_name))]
        for tag in tags:
            if tag.startswith('O:'):      # diagnostic oracle chains (NOT fair): see _oracle_root
                self.chains.append((tag, make(rt, inner_name)))
            elif tag.startswith('M:'):    # another player on the same noisy views, e.g. M:LIVEMR-K2-D
                self.chains.append((tag, make(rt, tag[2:])))
            else:
                self.chains.append((tag, NoiseRobustPlayer(rt, tag, make(rt, inner_name))))
        self.truth = make(rt, inner_name)
        self.name = f'FAN[{"|".join(tags)}]:{inner_name}'
        self.deadline_seconds = self.chains[0][1].deadline_seconds
        self.acc = {tag: Counter() for tag, _ in self.chains}
        self.inner = self.chains[0][1]
        self._truth_ctx = None

    @property
    def decisions(self):
        return self.inner.decisions

    def start(self, ctx):
        for tag, p in self.chains:
            p.start(ctx)
            if tag.startswith('O:'):
                p.search.root_fn = self._oracle_root(tag[2:], p)
        if self._truth_ctx is None or (self._truth_ctx.seed, self._truth_ctx.seat) != (ctx.seed, ctx.seat):
            self.truth.start(ctx)          # the truth chain's history is never rewritten: no resync restarts
            self._truth_ctx = ctx

    def act(self, view):
        from bot.noise.player import TRUTH
        tv = TRUTH['view']
        if tv is None:
            raise ValueError('FAN needs CAP: outermost')
        n_truth = len(self.truth.decisions)
        self.truth.act(tv)
        truth_dec = self.truth.decisions[-1] if len(self.truth.decisions) > n_truth else None
        out = None
        actions = {}
        for tag, p in self.chains:
            n = len(p.decisions)
            d = p.act(view)
            if out is None:
                out = d
            if len(p.decisions) > n:
                actions[tag] = p.decisions[-1]
        if truth_dec is not None and 'base' in actions:
            try:
                tb, nb = self.truth.search.p.belief, self.chains[0][1].search.p.belief
                err = float(nb.elixir) - float(tb.elixir)
                c = self.acc['base']
                c['bel_n'] += 1
                c['bel_err'] += err
                c['bel_abs'] += abs(err)
                c['bel_over2'] += err > 2
                c['bel_under2'] += err < -2
                c['bel_noisy10'] += nb.elixir >= 9.99
                c['bel_true10'] += tb.elixir >= 9.99
                c['bel_events_noisy'] = len(nb.events)
                c['bel_events_true'] = len(tb.events)
                td, nd = tb.derived(), nb.derived()
                if td.get('hand') is not None:
                    c['bel_hand_known'] += 1
                    c['bel_hand_same'] += nd.get('hand') is not None and set(nd['hand']) == set(td['hand'])
            except Exception as ex:
                self.acc['base']['bel_error'] += 1
        if truth_dec is not None and truth_dec.get('source') == 'search':
            last = getattr(self.truth.search.p.core, 'last', None) or {}
            scores = {int(a): s for a, s in zip(last.get('candidates', ()), last.get('scores', ())) if s is not None}
            if scores:
                best = max(scores.values())
                ta = int(truth_dec['action'])
                for tag, dec in actions.items():
                    c = self.acc[tag]
                    a = int(dec['action'])
                    c['n'] += 1
                    c['agree'] += a == ta
                    c['agree_play'] += (a < WAIT) == (ta < WAIT)
                    if a in scores:
                        c['scored'] += 1
                        c['regret'] += best - scores[a]
                    else:
                        c['outside'] += 1
                        c['regret_out_lb'] += best - min(scores.values())
                    c['src_' + dec.get('source', '?')] += 1
        return out

    def _oracle_root(self, what, chain):
        """Diagnostic only (reads the truth): the chain's search root with one part replaced by the true-sight
        twin's: 'units' = the true entity table; 'elix' = the true-sight belief's opponent elixir; 'opp' = a
        true-sight belief sample of the opponent (hand, cycle, elixir); 'all' = units + opp."""
        from dataclasses import replace
        from bot.noise.filter import with_entities, _entities
        from bot.noise.player import TRUTH
        R = self.truth.rt.R if hasattr(self.truth, 'rt') else None
        fair = self

        def root(info, opponent, rng):
            tb = fair.truth.search.p.belief
            if what in ('elix',):
                opponent = dict(opponent, elixir=float(tb.elixir))
            if what in ('opp', 'all'):
                opponent = tb.sample(rng)
            if what in ('units', 'all'):
                info = replace(info, packet=with_entities(info.packet, _entities(TRUTH['view'].info.packet)))
            elif what in ('ownu', 'oppu', 'recall', 'fp', 'unitrows', 'nonunit', 'recall2', 'attrs'):
                info = replace(info, packet=with_entities(info.packet, fair._mix_units(
                    what, _entities(info.packet), _entities(TRUTH['view'].info.packet))))
            return R.root(info, opponent, rng)
        return root

    def _mix_units(self, what, noisy, true):
        """Entity tables mixing the noisy and true units (towers from the noisy table): 'ownu' true own units,
        'oppu' true opponent units, 'recall' noisy + true units with no noisy unit of that owner within 1 tile,
        'fp' noisy units that have a true unit of that owner within 1 tile."""
        import math
        import numpy as np
        from bot.noise.player import tower_ids
        towers = getattr(self, '_towers', None)
        if towers is None:
            towers = self._towers = set(tower_ids(self.truth.rt))

        def unit(e):
            return e[0] not in towers and int(np.argmax(e[1][4:9])) <= 1

        def own(e):
            return e[1][2] > .5

        def near(e, pool):
            x, y = e[1][0]*18, e[1][1]*32
            return any(own(f) == own(e) and math.hypot(f[1][0]*18 - x, f[1][1]*32 - y) <= 1. for f in pool)
        keep = [e for e in noisy if not unit(e)]
        nu, tu = [e for e in noisy if unit(e)], [e for e in true if unit(e)]
        if what == 'ownu':
            return keep + [e for e in nu if not own(e)] + [e for e in tu if own(e)]
        if what == 'oppu':
            return keep + [e for e in nu if own(e)] + [e for e in tu if not own(e)]
        if what in ('recall2', 'attrs'):     # one-to-one greedy match within 1 tile, same owner
            cand = sorted((math.hypot(a[1][0]*18 - b[1][0]*18, a[1][1]*32 - b[1][1]*32), i, j)
                          for i, a in enumerate(nu) for j, b in enumerate(tu) if own(a) == own(b))
            ui, uj, pair = set(), set(), {}
            for d, i, j in cand:
                if d > 1.:
                    break
                if i in ui or j in uj:
                    continue
                ui.add(i); uj.add(j); pair[i] = j
            if what == 'recall2':         # every true unit without a partner is added (swarm members included)
                return keep + nu + [e for j, e in enumerate(tu) if j not in uj]
            # attrs: matched noisy units take the true row (position, hp, body, facing); others unchanged
            return keep + [tu[pair[i]] if i in pair else e for i, e in enumerate(nu)]
        if what == 'unitrows':       # true troop/building rows, noisy everything else (towers, no in-flight entities)
            return keep + tu
        if what == 'nonunit':        # noisy units + the true non-unit entities (projectiles, spells, effects, towers)
            return nu + [e for e in true if not unit(e)]
        if what == 'recall':
            return keep + nu + [e for e in tu if not near(e, nu)]
        return keep + [e for e in nu if near(e, tu)]

    def summary(self):
        return {tag: dict(c) for tag, c in self.acc.items()}

    def close(self):
        for _, p in self.chains:
            p.close()
        self.truth.close()


def make_fan(rt, name, make):
    import re
    m = re.fullmatch(r'FAN\[([^\]]*)\]:(.+)', name)
    tags = [t for t in m[1].split('|') if t]
    return FanPlayer(rt, tags, make, m[2])
