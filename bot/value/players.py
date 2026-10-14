"""K4S-st with a learned leaf value (exploration).

Name: 'K4SV-<model>' + optional tokens, e.g. K4SV-mlp1, K4SV-mlp1-h80, K4SV-lin1-x50.
- <model>  bot/value/model.py ValueModel.named(<model>) (BOT_VALUE_MODELS dir).
- h<T>     rollout horizon T ticks (coarse and refine), default 160.
- x<P>     leaf = phi + P/100 * (V - phi); default P=100 (pure V). V is in phi units
           (logit / k_phi of the phi-only fit), clipped to (-1.99, 1.99) so the frozen
           |x|<2 terminal rule and the WAIT bonus keep their meaning. Terminal leaves keep +-2.
- nost     drop the R3a top-8 student candidates (default: on, as K4S-st).
- e<P>     phi's elixir_weight = P/100 in every rollout (default 1.0 = frozen). With model 'phi'
           (no learned V, lambda 0) this is K4S-st with a recalibrated phi exchange rate.
Everything else is K4S-st (bot/search/players.py): frozen anchor.anytime phase order and
admission, S-default rule, candidates, belief, root. The rollout is
`rollout_commands` with exactly rollout_e1's arguments (identical leaf; bot/value/probe.py);
timed waits 2401/2402 stay on rollout_e1 and get the WAIT leaf's residual (V - phi) for the
same opponent style. Deterministic: no wall clock enters any decision.
"""
from __future__ import annotations

import json
import math
import re

from bot.players.base import WAIT
from bot.search.players import MultiSearchPlayer

CLIP = 1.99


def value_planner_class(base, model, lam, elixir_weight=None):
    import anchor
    import sdefault

    class ValuePlanner(base):
        def score_candidates(self, root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
            native, cfg = self.native, self.config
            cd, od, iv, ew = self.command_delay, self.opponent_delay, cfg.interval, cfg.elixir_weight
            if elixir_weight is not None:
                ew = elixir_weight
            tick = int(self.info.tick)
            used, resid, raw = [0.], {}, {}

            def evaluate(action, style, horizon, remaining, private):
                used[0] += horizon/cfg.horizon
                if action in (2401, 2402):
                    phi = native.rollout_e1(root, seat, action, style, cd, od, horizon, iv, ew, 1e6)
                    raw[action, style] = (phi, phi + resid.get(style, 0.))
                    return raw[action, style][1]
                phi, _, sim = native.rollout_commands(root, seat, action, [], style, cd, od, 1, 1, horizon, iv, iv, ew,
                                                      True, False, False)
                if abs(phi) >= 2. or model is None:
                    raw[action, style] = (phi, phi)
                    return phi
                pv = [json.loads(native.public_view(sim, s)) for s in (0, 1)]
                v = model.phi_units(pv, native.evaluation_parts(sim), seat, tick + horizon)
                v = max(-CLIP, min(CLIP, v))
                score = phi + lam*(v - phi)
                if action == WAIT:
                    resid[style] = score - phi
                raw[action, style] = (phi, score)
                return score
            action = anchor.anytime(self, root, seat, candidates, None, fallback,
                threads=1, coarse_horizon=self.coarse_horizon, clock=lambda: used[0], evaluate=evaluate,
                coarse_order=self.coarse_order, refine_proposals=self.refine_proposals)
            action = sdefault.apply_default(self, action, fallback, candidates)
            self.deadline_stats['rollouts'] = used[0]
            self.deadline_stats.update(self._diagnostics(raw, int(action)))
            return action

        def _diagnostics(self, raw, chosen):
            """Which action phi alone would pick from the same rollouts and work set (approximate: the
            top-8 refine set is the V one), and the best-vs-second gaps under each evaluator."""
            elixir = float(self.info.packet.observation.global_features[5])*10
            final = {}
            for a in self.last['candidates']:
                key = WAIT if a == 2400 else a
                styles = [raw.get((key, s)) for s in ('balanced', 'pressure', 'defense')]
                if any(x is None for x in styles):
                    continue
                pair = []
                for j in (0, 1):
                    x = sum(v[j] for v in styles)/3
                    ticks = {2400: 10, 2401: 20, 2402: 40}.get(a, 10 if a == WAIT else 0)
                    if ticks and abs(x) < 2:
                        x += .01*math.sqrt(ticks/20)*max(0., 1-elixir/10)
                    pair.append(x)
                final[a] = pair
            out = {}
            for j, tag in ((0, 'phi'), (1, 'v')):
                best = None
                for a in final:
                    if best is None or final[a][j] > final[best][j] + 1e-9:
                        best = a
                vals = sorted((x[j] for x in final.values()), reverse=True)
                out[f'{tag}_choice'] = best
                if len(vals) > 1:
                    out[f'{tag}_gap'] = vals[0] - vals[1]
            out['changed'] = float(out.get('phi_choice') != out.get('v_choice'))
            return out
    return ValuePlanner


class ValueSearchPlayer(MultiSearchPlayer):
    def __init__(self, rt, *, model, lam=1., horizon=160, student=True, elixir_weight=None, name=None):
        super().__init__(rt, student_candidates=student, horizon=horizon, name=name)
        from .model import ValueModel
        self.model = None if model == 'phi' else ValueModel.named(model)
        self.lam = 0. if model == 'phi' else lam
        self.elixir_weight = elixir_weight

    def start(self, ctx):
        super().start(ctx)
        core = self.p.core
        core.__class__ = value_planner_class(type(core), self.model, self.lam, self.elixir_weight)


def make_value_player(rt, name):
    tokens = name.split('-')
    if tokens[0] != 'K4SV' or len(tokens) < 2:
        raise ValueError(name)
    kw = dict(model=tokens[1], name=name)
    for t in tokens[2:]:
        m = re.fullmatch(r'([hxe])(\d+)', t)
        if m and m[1] == 'h':
            kw['horizon'] = int(m[2])
        elif m and m[1] == 'e':
            kw['elixir_weight'] = int(m[2])/100
        elif m:
            kw['lam'] = int(m[2])/100
        elif t == 'nost':
            kw['student'] = False
        else:
            raise ValueError(f'unknown value-search token {t!r} in {name!r}')
    return ValueSearchPlayer(rt, **kw)
