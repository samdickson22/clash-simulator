"""K4P-*: K4L-R-gs with pocket-aware changes (exploration). K4L-R-gs itself is untouched.

Tokens (any combination):
- kc<pct>  king credit. Once a princess tower of either side is down at the root, every rollout leaf (balanced coarse
           scan, waits and learned work set) adds kappa*(enemy king damage fraction if an enemy princess tower is
           dead) - kappa*(own king damage fraction if an own princess tower is dead), kappa = pct/100; terminal
           leaves (|v| >= 2) are unchanged. Reason: defense-v2 values a full king tower at 0.025 once one princess
           tower is down (0.25 x 0.10), about 8x less per HP than the remaining princess tower, so pocket pushes
           (which hit the king) score as almost worthless (reports/bot/pocket/RESULTS.md).
           Those decisions run the coarse scan through lopp.batch_rollouts with the scripted 'balanced' opponent
           (bit-identical to native rollout_e1, arm X) so the leaf state is available.
- h<T>     post-tower horizon: the same decisions roll out T ticks instead of 160.
- pw<n>    pocket work set. With an ENEMY princess tower down, up to 3 pocket tiles per legal troop/building card
           (bot.pocket.diag.pick_pocket) join the candidates, and the n best pocket plays by the balanced coarse
           scan join the learned work set (top-8 + waits) even when they miss the top-8. Reason: in the true-state
           sim a pocket play is a candidate at 89% of post-tower decisions but in the work set at only 43%; in the
           live replay s6-m01 (tick 880) a pocket Minions whose learned rollout kills the king (L = 2.0) was cut by
           the balanced coarse scan.
With no princess tower down a decision is exactly K4L-R-gs's (same code path, same values).
Names: 'K4P-' + '-'.join(tokens), e.g. K4P-kc30, K4P-kc30-h320, K4P-pw2, K4P-kc100-pw2.
"""
from __future__ import annotations

import json
import re

from bot.players.base import WAIT
from bot.search.lopp import (LearnedOppPlayer, batch_rollouts, fail_decision, fatal, mix, note_failure,
                             reduce_learned)
from bot.search.oppmodel import STYLES, TIMED_WAITS, _argmax, _bonus


def towers(native, sim, seat):
    """[own L, own R, own K, enemy L, enemy R, enemy K] health fractions (0 = dead), own frame."""
    return json.loads(native.public_view(sim, seat))['towers']


class KingLeaf:
    """Proxy for the native module: evaluate() adds the king-credit term; everything else is delegated."""

    def __init__(self, native, kappa):
        self._n, self.kappa = native, kappa

    def __getattr__(self, name):
        return getattr(self._n, name)

    def evaluate(self, sim, seat, elixir_weight):
        v = self._n.evaluate(sim, seat, elixir_weight)
        if abs(v) >= 2 or not self.kappa:
            return v
        t = towers(self._n, sim, seat)
        own_dead, enemy_dead = t[0] <= 0 or t[1] <= 0, t[3] <= 0 or t[4] <= 0
        # capped below a terminal win/loss (+-2): a credited non-terminal leaf never outranks a won rollout
        return max(-1.999, min(1.999, v + self.kappa * ((1 - t[5]) * enemy_dead - (1 - t[2]) * own_dead)))


def reduce_post_tower(core, root, seat, candidates, arm, *, kappa, horizon, coarse_order, make_opp, pocket=(),
                      pocket_work=0):
    """reduce_learned kind R with every rollout through batch_rollouts on a KingLeaf native."""
    original = list(candidates)
    plays = [a for a in original if a < WAIT]
    hinted = list(dict.fromkeys(a for a in coarse_order if a in plays))
    scan = hinted + [a for a in plays if a not in hinted]
    cfg = core.config
    native = KingLeaf(core.native, kappa)
    kw = dict(delay=core.command_delay, opp_delay=core.opponent_delay, horizon=horizon, interval=cfg.interval,
              elixir_weight=cfg.elixir_weight, tick0=int(core.info.tick))
    waits = [a for a in original if a >= WAIT and a != 2400]
    first = dict(zip(scan, batch_rollouts(native, root, seat, scan, STYLES[0], **kw))) if scan else {}
    chosen = set(sorted(plays, key=lambda a: (-first[a], original.index(a)))[:arm.get('top', 8)])
    pk = [a for a in plays if a in set(pocket)]
    chosen.update(sorted(pk, key=lambda a: (-first[a], original.index(a)))[:pocket_work])
    work = [a for a in original if a >= WAIT or a in chosen]
    keys = [a for a in original if (a >= WAIT and a != 2400) or a in chosen]
    wv = dict(zip(waits, batch_rollouts(native, root, seat, waits, STYLES[0], **kw))) if waits else {}
    L = dict(zip(keys, batch_rollouts(native, root, seat, keys, make_opp(0), **kw)))
    scores = {}
    for a in work:
        k = WAIT if a == 2400 else a
        b = first[k] if k < WAIT else wv[k]
        scores[a] = mix(b, L[k], arm.get('lw'))
    elixir = float(core.info.packet.observation.global_features[5]) * 10
    for a in scores:
        scores[a] = _bonus(a, scores[a], elixir)
    best = _argmax(work, scores)
    core.last = dict(candidates=work, scores=[scores.get(a) for a in work], traces=[])
    core.deadline_stats = dict(hit=False, fallback=best is None, completed=len(scores), candidates=len(work))
    n = len(scan) + len(waits)
    return best, dict(rollouts=n + len(keys), native=n, learned=len(keys), post_tower=1)


class PocketPlayer(LearnedOppPlayer):
    def __init__(self, rt, *, kappa=0., horizon=160, pocket_work=0, name=None):
        super().__init__(rt, arm=dict(kind='R'), model='pool', sample=True, name=name)
        self.kappa, self.post_horizon, self.pocket_work = kappa, horizon, pocket_work

    def start(self, ctx):
        super().start(ctx)
        import sdefault
        from bot.search.lopp import Learned, load_model, sample_seed
        from bot.pocket.diag import Kinds, classify, dead, pick_pocket, pocket_actions
        core, inner = self.p.core, self.p.core.score_candidates
        model, seed = load_model('pool'), ctx.seed
        kinds, orig_candidates, self._pocket = Kinds(self.rt.R.builder), core.candidates, ()

        def candidates(packet, policy_proposals=()):
            out, mask = orig_candidates(packet, policy_proposals)
            self._pocket = ()
            obs = packet.observation
            gf = [float(x) for x in obs.global_features]
            if self.pocket_work and (dead(gf)[0] or dead(gf)[1]):
                hand = [kinds(int(t)) for t in list(obs.hand_ids)[:4]]
                legal = pocket_actions(mask, hand, gf)
                extra = [a for a in pick_pocket(legal, gf) if a not in out]
                out = list(out) + extra
                self._pocket = tuple(a for a in out if a < 2304 and classify(a, hand, gf) == 'pocket')
            return out, mask
        core.candidates = candidates

        def make_opp(j=0):
            return Learned(model, True, None, 5, seed=sample_seed([seed, int(core.info.tick)], j))

        def score_candidates(root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
            t = towers(core.native, root, seat)
            if all(x > 0 for x in t[:2] + t[3:5]):
                return inner(root, seat, candidates, trace=trace, deadline=deadline, fallback=fallback)
            try:
                action, info = reduce_post_tower(core, root, seat, candidates, self.arm, kappa=self.kappa,
                                                 horizon=self.post_horizon, coarse_order=core.coarse_order,
                                                 make_opp=make_opp, pocket=self._pocket,
                                                 pocket_work=self.pocket_work)
            except BaseException as ex:
                if fatal(ex):
                    raise
                note_failure('pocket', ex)
                fail_decision(core, candidates, 'pocket')
                action, info = None, dict(rollouts=0, native=0, learned=0, native_failure='pocket')
            action = fallback if action is None else action
            core.selected_wait_ticks = TIMED_WAITS.get(action, 0)
            action = sdefault.apply_default(core, action, fallback, candidates)
            core.deadline_stats['rollouts'] = info['rollouts']
            self._dec = info
            return action
        core.score_candidates = score_candidates


def make_pocket_player(rt, name):
    kw = {}
    for token in name.split('-')[1:]:
        if m := re.fullmatch(r'kc(\d+)', token):
            kw['kappa'] = int(m[1]) / 100
        elif m := re.fullmatch(r'h(\d+)', token):
            kw['horizon'] = int(m[1])
        elif m := re.fullmatch(r'pw(\d+)', token):
            kw['pocket_work'] = int(m[1])
        else:
            raise ValueError(f'unknown pocket token {token!r} in {name!r}')
    return PocketPlayer(rt, name=name, **kw)
