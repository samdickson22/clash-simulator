"""Live-root candidate scores and defend-vs-WAIT counterfactuals (bot lead live-diag, exploration tier).

Replays a logged live match (RUN/perception.jsonl, the exact LiveSession.step records) through the live harness as
bot/pocket/live_replay.py does: LiveTranslator + LiveSession + LivePlayer (fast tier and cutoff default = --fast,
rl5 v10 live), with the search tier replaced by its deterministic twin K4L-R-gs-rw (no wall clock; the live search
completed in <= 122 ms on every logged decision, so the twin makes the live choices up to the rw low bits).

Per search decision (kind 'search'): tick, elixir, hand, enemy units on our half, the chosen action / card, the
candidate list's cards and whether R3a proposed them, and the search's own work-set scores (core.last) grouped by
card: best score per card, WAIT's, the chosen one's.

Counterfactual (kind 'cf') at decisions with an enemy ground unit on our half or an enemy Giant anywhere (every
--cf-every ticks): a fixed defence set re-scored on the decision's own root with K4L-R's scorer
((balanced rollout_e1 + learned pool-gs rw)/2 + timed-wait bonus, horizon 160) under variants
  d<T>      our command delay T ticks (live models 27 = 1.35 s), opponent delay 27;
  lv        bot/levels/root.ExactLevelRoot with the account's true levels (profile.OWN_LEVELS, towers 6/6) and the
            fair opponent estimate (profile.OpponentEstimate), plus the level leaf native; delay 27.
The defence set: chosen, WAIT, and per legal hand card a few tiles: troops in front of the threatened princess tower
and at our bridge, Cannon at the centre-pull tiles and in front of the tower, Fireball on the enemy group on our
half (and the enemy princess towers), Giant at our back corner and bridge. Read-only: nothing is played.

    python -m bot.livediag.root_scores RUN --out FILE.jsonl --fast student:<rl5 v10>@0.5375 [--cf-every 10]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

WAIT = 2304
DELAYS = (5, 10, 20, 27, 40)


def tile_id(x, y):
    return int(y) * 18 + int(x)


class Diag:
    """Logging wrapper around the deterministic K4L-R search (call signature of LivePlayer's search tier)."""

    def __init__(self, inner, rt, sink, meta, cf_every, level_root=None, level_native=None):
        from bot.pocket.diag import Kinds
        self.inner, self.rt, self.sink, self.meta, self.cf_every = inner, rt, sink, meta, cf_every
        self.name, self.deadline_seconds = inner.name, None
        self.kinds = Kinds(rt.R.builder)
        self.level_root, self.level_native = level_root, level_native

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def start(self, ctx):
        self.inner.start(ctx)
        self.ctx = ctx
        core = self.core = self.inner.p.core
        orig_c, orig_s = core.candidates, core.score_candidates

        def candidates(packet, policy_proposals=()):
            out, mask = orig_c(packet, policy_proposals)
            self._cand = (list(out), mask, [int(a) for a in policy_proposals])
            return out, mask

        def score_candidates(root, seat, cands, **kw):
            self._root = (root, seat)
            return orig_s(root, seat, cands, **kw)
        core.candidates, core.score_candidates = candidates, score_candidates

    def close(self):
        self.inner.close()

    def emit(self, row):
        self.sink.write(json.dumps(dict(self.meta, **row)) + '\n')
        self.sink.flush()

    def act(self, view, *, wall0=None, default=None):
        self._cand, self._root = None, None
        d = self.inner.act(view)
        if d.stats is None or self._cand is None:
            return d
        try:
            self.log(view, d)
        except Exception as ex:          # diagnosis must never change the replayed decision
            self.emit(dict(kind='log_error', tick=view.tick, error=repr(ex)[:300]))
        return d

    # -- state ------------------------------------------------------------------------------------------------------
    def board(self, view):
        obs = view.reserved.packet.observation
        names = self.rt.R.builder.token_names
        units = []
        for i in [int(j) for j in obs.entity_mask.nonzero()[0]]:
            f, tok = obs.entity_features[i], int(obs.entity_ids[i])
            name = names[tok] if 0 <= tok < len(names) else str(tok)
            if name in ('Tower', 'KingTower') or not (f[4] > .5 or f[5] > .5):   # towers; spells/shots
                continue
            units.append((name, 'own' if f[2] > .5 else 'enemy', round(float(f[0]) * 18, 2),
                          round(float(f[1]) * 32, 2), round(float(f[9]), 3)))
        return units

    def log(self, view, d):
        from bot.pocket.diag import view_state
        gf, hand, _ = view_state(view, self.rt.R.builder, self.kinds)
        cards = [h[0] for h in hand]
        units = self.board(view)
        enemy_ours = [u for u in units if u[1] == 'enemy' and u[3] < 16]
        giant = [u for u in units if u[1] == 'enemy' and u[0] == 'Giant']
        cands, mask, props = self._cand
        last = self.core.last or {}
        scores = {int(a): s for a, s in zip(last.get('candidates') or [], last.get('scores') or []) if s is not None}
        a = int(d.action)
        key = {10: 2400, 20: 2401, 40: 2402}.get(d.wait_ticks, a) if a >= WAIT else a
        best = {}
        for c, s in scores.items():
            k = 'WAIT' if c >= WAIT else cards[c // 576]
            if k not in best or s > best[k][0]:
                best[k] = (round(s, 5), c)
        elixir = round(gf[5] * 10, 2)
        row = dict(kind='search', tick=view.tick, elixir=elixir, hand=cards, action=a, wait_ticks=d.wait_ticks,
                   card=cards[a // 576] if a < WAIT else None, source=(d.stats or {}).get('source'),
                   enemy_ours=enemy_ours, giant=giant,
                   cand_cards={k: sum(1 for c in cands if c < WAIT and cards[c // 576] == k) for k in set(cards)},
                   prop_cards={k: sum(1 for c in props if c < WAIT and cards[c // 576] == k) for k in set(cards)},
                   n_cand=len(cands), legal_cards=sorted({cards[s] for s in range(4) if mask[s*576:(s+1)*576].any()}),
                   best=best, chosen_score=scores.get(key), wait_score=scores.get(WAIT))
        self.emit(row)
        if self.cf_every and (enemy_ours or giant) and view.tick % self.cf_every == 0 and self._root is not None:
            keys = self.defence_set(key, cards, mask, units, gf)
            self.emit(dict(kind='cf', tick=view.tick, elixir=elixir, hand=cards, chosen=key, enemy_ours=enemy_ours,
                           giant=giant, **self.counterfactual(view, keys, cards)))

    def defence_set(self, chosen, cards, mask, units, gf):
        enemy = [u for u in units if u[1] == 'enemy' and u[3] < 16] or [u for u in units if u[1] == 'enemy'
                                                                       and u[0] == 'Giant']
        lx = 3 if (sorted(u[2] for u in enemy)[len(enemy)//2] if enemy else 9) < 9 else 14
        side = -1 if lx == 3 else 1
        want = {'troop': [(lx, 10), (lx + side * -2, 11), (lx, 13)],
                'Cannon': [(8, 10), (9, 10), (lx + side * -2, 10)],
                'Giant': [(lx, 1), (lx, 13)]}
        keys = [chosen, WAIT]
        for slot, card in enumerate(cards):
            if not mask[slot*576:(slot+1)*576].any():
                continue
            if card == 'Fireball':
                tiles = []
                if enemy:
                    cx = sum(u[2] for u in enemy) / len(enemy)
                    cy = sum(u[3] for u in enemy) / len(enemy)
                    tiles.append((cx, cy))
                tiles += [(3, 25), (14, 25)]
            else:
                tiles = want.get(card, want['troop'])
            for x, y in tiles:
                t = tile_id(min(17, max(0, x)), min(31, max(0, y)))
                legal = [tt for tt in range(576) if mask[slot*576 + tt]]
                if not legal:
                    continue
                t = min(legal, key=lambda tt: ((tt % 18) - (t % 18)) ** 2 + ((tt // 18) - (t // 18)) ** 2)
                keys.append(slot*576 + t)
        return list(dict.fromkeys(int(k) for k in keys))

    def counterfactual(self, view, keys, cards):
        from bot.search.lopp import Learned, batch_rollouts, load_model, mix
        from bot.search.oppmodel import _bonus
        core, (root, seat) = self.core, self._root
        cfg = core.config
        elixir = float(core.info.packet.observation.global_features[5]) * 10
        tick = int(core.info.tick)
        rk = [WAIT if k == 2400 else k for k in keys]
        out = dict(keys=keys, cards=[cards[k // 576] if k < WAIT else None for k in keys],
                   tiles=[((k % 576) % 18, (k % 576) // 18) if k < WAIT else None for k in keys])

        def score(native, r, delay):
            b = [native.rollout_e1(r, seat, a, 'balanced', delay, core.opponent_delay, cfg.horizon, cfg.interval,
                                   cfg.elixir_weight, 1e6) for a in rk]
            opp = Learned(load_model('pool'), True, None, 5, seed=[self.ctx.seed, tick], rowwise=True)
            L = batch_rollouts(native, r, seat, rk, opp, delay=delay, opp_delay=core.opponent_delay,
                               horizon=cfg.horizon, interval=cfg.interval, elixir_weight=cfg.elixir_weight,
                               tick0=tick)
            return [round(_bonus(k, mix(bv, lv), elixir), 6) for k, bv, lv in zip(keys, b, L)], \
                   [round(x, 6) for x in b], [round(x, 6) for x in L]
        for dl in DELAYS:
            out[f'd{dl}'], out[f'd{dl}_b'], out[f'd{dl}_L'] = score(core.native, root, dl)
        if self.level_root is not None:
            # L11 vs true levels on ONE opponent sample: the search's own sample if the level export covers its cards,
            # else a fresh belief sample (keyed rng) for which BOTH roots are rebuilt (lv11 = R.root on that sample).
            import numpy as np
            info, opp_state, root11 = core.info, self.last_opponent, root
            for j in range(9):
                try:
                    r2 = self.level_root(info, opp_state, np.random.default_rng([self.ctx.seed, tick, 0x1e, j]))
                    break
                except ValueError as ex:
                    out['lv_error'] = repr(ex)[:200]
                    rng = np.random.default_rng([self.ctx.seed, tick, 0x5a, j])
                    opp_state = self.inner.p.belief.sample(rng)
                    root11 = self.rt.R.root(info, opp_state, rng)
            else:
                return out
            out['lv_resampled'] = j
            out['lv'], out['lv_b'], out['lv_L'] = score(self.level_native or core.native, r2, core.command_delay)
            if j:
                out['lv11'], out['lv11_b'], out['lv11_L'] = score(core.native, root11, core.command_delay)
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run', type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--fast', required=True)
    ap.add_argument('--search', default='K4L-R-gs-rw')
    ap.add_argument('--cf-every', type=int, default=10)
    ap.add_argument('--levels', action='store_true', help='also score the level-aware root (lv variant)')
    a = ap.parse_args()
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.live.player import LivePlayer
    from bot.live.translate import LiveSession, LiveTranslator
    from bot.eval.headline import make_player
    cfg = json.loads((a.run / 'session-config.json').read_text())
    rt = Runtime()
    sink = open(a.out, 'w')
    level_root = level_native = None
    if a.levels:
        from bot.levels.profile import OWN_LEVELS, OWN_TOWER, OPP_TOWER, OpponentEstimate
        from bot.levels.root import ExactLevelRoot, leaf_native
        lr = ExactLevelRoot(rt, OWN_LEVELS, OpponentEstimate(rt), OWN_TOWER, OPP_TOWER, force=True)
        level_root, level_native = lr.root, leaf_native(rt, OWN_TOWER, OPP_TOWER)
    live = LivePlayer(rt, tier='search', fast_spec=a.fast, cutoff_default='it5s2', name=cfg['player'] + '~diag')
    diag = Diag(make_player(rt, a.search), rt, sink, dict(run=a.run.name), a.cf_every, level_root, level_native)
    live.search = diag
    tcfg, scfg = cfg['translator'], cfg['session']
    tr = LiveTranslator(rt, cfg['deck'], unknown_card=tcfg['unknown_card'], plays_from=tcfg['plays_from'])
    s = LiveSession(rt, live, cfg['deck'], seed=scfg['seed'], command_delay=scfg['command_delay'],
                    expire=scfg['expire'], translator=tr)
    # the level root needs the same belief sample the search root used: capture it from belief.sample
    errors = 0
    started = False
    for line in open(a.run / 'perception.jsonl'):
        rec = json.loads(line)
        rec['elixir'] = max(rec['elixir'], sum(c.cost for c in s.ch.pending))
        if rec.get('tick') is not None:
            rec['tick'] = int(rec['tick'])
        try:
            d = s.step(rec)
        except Exception as ex:
            errors += 1
            sink.write(json.dumps(dict(run=a.run.name, kind='error', tick=rec.get('tick'), error=repr(ex)[:300])) + '\n')
            continue
        if not started and getattr(diag, 'core', None) is not None:
            started = True
            belief = diag.inner.p.belief
            orig = belief.sample

            def sample(rng, *, deadline=None, _orig=orig):
                out = _orig(rng, deadline=deadline)
                diag.last_opponent = out
                return out
            belief.sample = sample
    s.close()
    sink.write(json.dumps(dict(run=a.run.name, kind='end', errors=errors, tr_stats=dict(tr.stats))) + '\n')


if __name__ == '__main__':
    main()
