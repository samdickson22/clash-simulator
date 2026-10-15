"""Learned rollout opponent inside K4C-r16's scorer (exploration).

K4C-r16 scores candidates with 160-tick native `rollout_e1` rollouts against three scripted opponents. Here the
rollout is driven from Python on the same Rust clone (BattleState.clone/step, NativeScripts.select_action /
apply_discrete / evaluate), so the opponent side can be a learned policy that acts on native public_view /
public_mask features of its own seat (bot/search/lopp_feat.py, trained by bot/search/lopp_train.py on v1/R3a
decisions recorded by bot/search/lopp_record.py).

`batch_rollouts` reproduces `rollout_e1` (= wait_command_simulation with capacity 1, continue_own, no endpoint):
per tick k < horizon: decisions at 0 < k with k % interval == 0 (own 'balanced' when its channel is free and
k >= the timed-wait length, then the opponent), then executions of due commands (own, then opponent), then one
tick. With capacity 1 a choice is only made on an empty channel, so the reservation shadowing of the native
loop never applies. All candidates of a decision run in lockstep, so the learned opponent's forward is batched.
With a scripted opponent it is bit-identical to rollout_e1 (arm X; see PROGRESS.md).

Names 'K4L-' + tokens (candidates, coarse scan, refine, timed-wait bonus, S-default as K4C-r16):
- X        frozen mean of the 3 scripted styles, every rollout by the Python loop (exactness check: == K4C-r16)
- M<pct>   frozen 3-style mean score s; final = (1-w)*s + w*L on the work set (WAIT, timed waits, top-8 plays)
           with L = learned-opponent rollout value. M0 == K4C-r16.
- R        balanced coarse scan; top-8 + waits scored (balanced + L)/2 (pressure/defense replaced by L).
- L        learned opponent only: every candidate scored by L (no coarse/refine split).
- m<name>  model file $CLASHER_LOPP_MODELS/<name>.npz (default pool)
- gs       sampled gate/card with common random numbers across candidates (default: calibrated threshold)
- rw       row-wise forward (one state per numpy call): the float32 forward of a batch depends on its composition
           (BLAS blocking), a single row does not, so rw values do not depend on how rollouts are batched;
           single-row calls are also ~3x cheaper than 2-3-row batches. Differs from the batched forward in the
           low bits only.
- h<N>     learned opponent for the first N rollout ticks, scripted balanced afterwards
- i<I>     learned opponent decision interval (default 5 = the real players' poll cadence)
- t/c/p/w  threads, chunks, worker processes, wall deadline (kind R only): bot/search/lopp_fast.py
Deterministic: no wall clock; gs uniforms are keyed by (match seed, tick, rollout tick).
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from pathlib import Path

import numpy as np

from bot.players.base import WAIT
from bot.search.candidates import CandidateSearchPlayer
from bot.search.oppmodel import STYLES, TIMED_WAITS, _argmax, _bonus

_MODELS: dict = {}


def load_model(name):
    if name not in _MODELS:
        from bot.search.lopp_feat import NumpyOpponent
        root = Path(os.environ.get('CLASHER_LOPP_MODELS', '/mpac/sdicks02/jobs/clasher/bot-lopp-models'))
        _MODELS[name] = NumpyOpponent(root / f'{name}.npz')
    return _MODELS[name]


class Learned:
    """Opponent controller: model + gate mode + optional switch to scripted balanced after `switch` ticks."""

    def __init__(self, model, sample=False, switch=None, interval=5, seed=0, rowwise=False):
        self.m, self.sample, self.switch, self.interval, self.seed = model, sample, switch, interval, seed
        self.rowwise = rowwise
        self.calls = self.plays = 0
        self.elixir_at_play = 0.

    def decide(self, native, sims, idxs, seat, tick):
        from bot.search.lopp_feat import NGLOB, featurize
        m = self.m
        X, cards = [], []
        for i in idxs:
            view = json.loads(native.public_view(sims[i], seat))
            x, hand = featurize(view, tick, m.cost_of)
            X.append(x); cards.append([m.vocab.get(t, 0) for t in hand])
        X, cards = np.stack(X), np.asarray(cards)
        if self.rowwise:    # one row per forward: values independent of the batch composition (rw)
            h = np.concatenate([m.trunk(X[r:r+1], cards[r:r+1]) for r in range(len(idxs))])
            heads = [m.heads(h[r:r+1]) for r in range(len(idxs))]
            gate, vlog = np.concatenate([g for g, _ in heads]), np.concatenate([v for _, v in heads])
        else:
            h = m.trunk(X, cards)
            gate, vlog = m.heads(h)
        p = 1 / (1 + np.exp(-gate[:, 0]))
        u = np.random.default_rng([*self.seed, tick]).random(2) if self.sample else None
        out = []
        self.calls += len(idxs)
        for r, i in enumerate(idxs):
            # WAIT if the gate says wait or nothing is legal; the mask is only built after the gate passes.
            if not (u[0] < p[r] if self.sample else p[r] >= m.tau):
                out.append(WAIT)
                continue
            mask = np.asarray(native.public_mask(sims[i], seat), dtype=bool)[:2304].reshape(4, 576)
            legal = mask.any(axis=1)
            if not legal.any():
                out.append(WAIT)
                continue
            logits = np.where(legal, vlog[r][cards[r]], -np.inf)
            if self.sample:
                q = np.exp(logits - logits.max()); q /= q.sum()
                slot = int(min(np.searchsorted(np.cumsum(q), u[1]), 3))
                slot = slot if legal[slot] else int(np.argmax(logits))
            else:
                slot = int(np.argmax(logits))
            t = m.tiles(h[r:r+1], cards[r:r+1, slot])[0]
            tile = int(np.argmax(np.where(mask[slot], t, -np.inf)))
            out.append(slot * 576 + tile)
            self.plays += 1
            self.elixir_at_play += float(X[r, -NGLOB]) * 10
        return out


def batch_rollouts(native, root, seat, actions, opponent, *, delay, opp_delay, horizon=160, interval=10,
                   elixir_weight=1.0, tick0=0, deadline=None):
    """Values of `actions` (plays, WAIT, timed waits 2400-2402). opponent: a style name or a Learned.
    deadline: time.monotonic() cutoff checked between steps; past it the batch returns None (values unchanged
    otherwise)."""
    n = len(actions)
    sims = [root.clone() for _ in range(n)]
    opp = 1 - seat
    waits = [TIMED_WAITS.get(a, 0) for a in actions]
    own = [None if (a >= WAIT) else (delay, a) for a in actions]    # (due tick, action); capacity 1
    oq = [None] * n
    learned = not isinstance(opponent, str)

    def opp_decide(k, idxs):
        if not idxs:
            return
        if learned and (opponent.switch is None or k < opponent.switch):
            if k % opponent.interval:
                return
            acts = opponent.decide(native, sims, idxs, opp, tick0 + k)
        else:
            if k % interval:
                return
            style = 'balanced' if learned else opponent
            acts = [native.select_action(sims[i], opp, style) for i in idxs]
        for i, a in zip(idxs, acts):
            if a != WAIT:
                oq[i] = (k + opp_delay, a)

    opp_decide(0, list(range(n)))
    step = math.gcd(interval, opponent.interval) if learned else interval
    k = 0
    while k < horizon:
        if deadline is not None and time.monotonic() >= deadline:
            return None
        if k > 0:
            if k % interval == 0:
                for i in range(n):
                    if own[i] is None and k >= waits[i]:
                        a = native.select_action(sims[i], seat, 'balanced')
                        if a != WAIT:
                            own[i] = (k + delay, a)
            opp_decide(k, [i for i in range(n) if oq[i] is None])
        end = min(horizon, k + step)
        for i in range(n):
            cur = k
            while True:
                if own[i] is not None and own[i][0] <= cur:
                    native.apply_discrete(sims[i], seat, own[i][1]); own[i] = None
                if oq[i] is not None and oq[i][0] <= cur:
                    native.apply_discrete(sims[i], opp, oq[i][1]); oq[i] = None
                nxt = min([q[0] for q in (own[i], oq[i]) if q is not None and cur < q[0] < end] + [end])
                sims[i].step(nxt - cur)
                cur = nxt
                if cur >= end:
                    break
        k = end
    return [native.evaluate(s, seat, elixir_weight) for s in sims]


def reduce_learned(core, root, seat, candidates, arm, *, coarse_order=(), refine_proposals=(), make_opp=None):
    """K4C-r16's anytime reduction (oppmodel.reduce_scores, weights=None) with the learned-opponent arms."""
    original = list(candidates)
    if WAIT not in original or len(set(original)) != len(original):
        raise ValueError('unique candidates including WAIT required')
    plays = [a for a in original if a < WAIT]
    hinted = list(dict.fromkeys(a for a in coarse_order if a in plays))
    scan = hinted + [a for a in plays if a not in hinted]
    cfg = core.config
    kw = dict(delay=core.command_delay, opp_delay=core.opponent_delay, horizon=cfg.horizon,
              interval=cfg.interval, elixir_weight=cfg.elixir_weight, tick0=int(core.info.tick))
    kind = arm['kind']
    nat, n_native, n_learned = {}, [0], [0]

    def native_values(keys, style):
        keys = [a for a in keys if (a, style) not in nat]
        if not keys:
            return
        if kind == 'X':
            vals = batch_rollouts(core.native, root, seat, keys, style, **kw)
        else:
            vals = [core.native.rollout_e1(root, seat, a, style, core.command_delay, core.opponent_delay,
                                           cfg.horizon, cfg.interval, cfg.elixir_weight, 1e6) for a in keys]
        nat.update({(a, style): v for a, v in zip(keys, vals)})
        n_native[0] += len(keys)

    def learned_values(keys):
        keys = list(dict.fromkeys(keys))
        vals = batch_rollouts(core.native, root, seat, keys, make_opp(), **kw)
        n_learned[0] += len(keys)
        return dict(zip(keys, vals))

    scores = {}
    if kind == 'L':
        keys = [WAIT if a == 2400 else a for a in original]
        L = learned_values(keys)
        for a, k in zip(original, keys):
            scores[a] = L[k]
        work = original
    else:
        waits = [a for a in original if a >= WAIT and a != 2400]
        native_values(scan, STYLES[0])
        first = {a: 0. + nat[a, STYLES[0]] for a in scan}
        chosen = set(sorted(plays, key=lambda a: (-first[a], original.index(a)))[:8])
        chosen.update(a for a in refine_proposals if a in plays)
        work = [a for a in original if a >= WAIT or a in chosen]
        keys = [a for a in original if (a >= WAIT and a != 2400) or a in chosen]
        native_values(waits, STYLES[0])
        if kind in ('X', 'M'):
            for style in STYLES[1:]:
                native_values(keys, style)
        L = learned_values(keys) if kind == 'R' or (kind == 'M' and arm['w'] > 0) else {}
        for a in work:
            k = WAIT if a == 2400 else a
            b = first[k] if k < WAIT else nat[k, STYLES[0]]
            if kind == 'R':
                scores[a] = (b + L[k]) / 2
                continue
            s = b/3 if k < WAIT else 0. + b/3          # frozen order: ((b/3) + p/3) + d/3
            for style in STYLES[1:]:
                s += nat[k, style]/3
            scores[a] = s if kind == 'X' or arm['w'] == 0 else (1 - arm['w'])*s + arm['w']*L[k]
    elixir = float(core.info.packet.observation.global_features[5])*10
    for a in scores:
        scores[a] = _bonus(a, scores[a], elixir)
    best = _argmax(work, scores)
    core.last = dict(candidates=work, scores=[scores.get(a) for a in work], traces=[])
    core.deadline_stats = dict(hit=False, fallback=best is None, completed=len(scores), candidates=len(work))
    return best, dict(rollouts=n_native[0] + n_learned[0], native=n_native[0], learned=n_learned[0])


class LearnedOppPlayer(CandidateSearchPlayer):
    def __init__(self, rt, *, arm, model='pool', sample=False, switch=None, interval=5, rowwise=False, name=None):
        super().__init__(rt, r3a=16, second=0, name=name)
        self.arm, self.model_name = arm, model
        self.sample, self.switch, self.interval, self.rowwise = sample, switch, interval, rowwise

    def start(self, ctx):
        super().start(ctx)
        import sdefault
        core = self.p.core
        model = load_model(self.model_name) if self.arm['kind'] != 'X' else None
        self._dec, self.opp_calls, self.opp_plays = {}, 0, 0
        seed = ctx.seed

        def make_opp():
            return Learned(model, self.sample, self.switch, self.interval, seed=[seed, int(core.info.tick)],
                           rowwise=self.rowwise)

        def score_candidates(root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
            action, info = reduce_learned(core, root, seat, candidates, self.arm, coarse_order=core.coarse_order,
                                          refine_proposals=core.refine_proposals, make_opp=make_opp)
            action = fallback if action is None else action
            core.selected_wait_ticks = TIMED_WAITS.get(action, 0)
            action = sdefault.apply_default(core, action, fallback, candidates)
            core.deadline_stats['rollouts'] = info['rollouts']
            self._dec = info
            return action
        core.score_candidates = score_candidates

    def act(self, view):
        self._dec = {}
        return super().act(view)

    def _done(self, action, stats, wall0, wait_ticks=0):
        return super()._done(action, dict(stats, **self._dec), wall0, wait_ticks)


def make_lopp_player(rt, name):
    """'K4L-' + tokens (module docstring), e.g. K4L-X, K4L-M0, K4L-M50, K4L-R, K4L-L-mR3a-gs-h60.
    t<N>/c<P>/p<P>/w<ms> (threads, chunks, worker processes, wall deadline): bot/search/lopp_fast.py."""
    kw, arm, fast = {}, None, {}
    for token in name.split('-')[1:]:
        if token in ('X', 'R', 'L'):
            arm = dict(kind=token)
        elif m := re.fullmatch(r'M(\d+)', token):
            arm = dict(kind='M', w=int(m[1])/100)
        elif m := re.fullmatch(r'm([\w.]+)', token):
            kw['model'] = m[1]
        elif token == 'gs':
            kw['sample'] = True
        elif token == 'rw':
            kw['rowwise'] = True
        elif token == 'fp':                                 # bot/search/lopp_fast.py
            fast['fast_prep'] = True
        elif m := re.fullmatch(r'h(\d+)', token):
            kw['switch'] = int(m[1])
        elif m := re.fullmatch(r'i(\d+)', token):
            kw['interval'] = int(m[1])
        elif m := re.fullmatch(r'([tcpw])(\d+)', token):   # bot/search/lopp_fast.py
            fast[dict(t='threads', c='chunks', p='pool', w='wall_ms')[m[1]]] = int(m[2])
        else:
            raise ValueError(f'unknown learned-opponent token {token!r} in {name!r}')
    if arm is None:
        raise ValueError(name)
    if fast:
        from bot.search.lopp_fast import make_fast_player
        return make_fast_player(rt, name, arm, dict(kw, **fast))
    return LearnedOppPlayer(rt, arm=arm, name=name, **kw)
