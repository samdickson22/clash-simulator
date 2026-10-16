"""Pocket diagnostic: does K4L-R-gs push the pocket after taking a princess tower? (exploration)

Plays HEADLINE cases in our engine (bot.players.ours.play_match, true state) with a logging wrapper around each
candidate player. The wrapper only reads: it never changes a decision (check: --no-cf games have the same
command_sha256 as bot.eval.headline's).

Per decision it writes DIR/dec-<worker>.jsonl rows:
- search players (K4L-*, K4C-*): every searched decision: tick, tower fractions (own L/R/K, enemy L/R/K, own
  frame), elixir, threats (enemy non-tower bodies in our half), the chosen action and its class, the candidate
  list's classes (how many pocket plays, how many of them from R3a's proposals, how many in the refined work set),
  the pocket-legal troop actions in the placement mask, and the best pocket score vs the chosen score.
- policy players (R3a, v1): every play, plus the placement mask's pocket-legal count once a tower is down.
- tower rows whenever a tower falls.
Action classes (own frame, row 0 = own king edge): wait; spell_own/spell_enemy (row >= 16 = enemy half);
pocket (troop/building in rows 17-20 on the side of a dead enemy princess tower, the engine's expanded zone,
arena.get_deploy_zones); enemy (other enemy-half placements, e.g. Miner); bridge (rows 13-16); back (rows <= 12).

Search counterfactual (--cf-every N, search players only): at decisions with an enemy princess tower down, the
chosen action not a pocket play and tick % N == 0, it re-scores, on the decision's own root, the chosen action,
WAIT and up to 3 pocket tiles per legal troop/building card (plus the pocket plays already in the candidate list)
with K4L-R-gs's own scorer ((balanced native + learned pool-gs)/2 + timed-wait bonus) at horizons 160/320/480.
The rollouts clone the root and use keyed RNGs, so the game is unchanged.

Forced counterfactual (--force FILE): replays a game and, at one decision tick, plays a given action instead of
the search's choice (true-outcome test of "pocket instead of what K4L did").

    python -m bot.pocket.diag --out DIR --candidate K4L-R-gs,R3a,v1 --opponents R3a,v1 --games 300 --workers 40
"""
from __future__ import annotations

import argparse
import json
import os
import time
from multiprocessing import Process
from pathlib import Path

WAIT = 2304
TIMED_WAITS = {2400: 10, 2401: 20, 2402: 40}
HORIZONS = (160, 320, 480)
GF_TOWERS = slice(8, 14)   # own L, R, K, enemy L, R, K (own-frame lanes)


class Kinds:
    """Card name -> ('spell' | 'building' | 'troop', can_deploy_on_enemy_side)."""

    def __init__(self, builder):
        self.b, self.cache = builder, {}

    def __call__(self, token):
        if token not in self.cache:
            from clasher.card_aliases import resolve_card_name
            from clasher.spells import SPELL_REGISTRY
            name = self.b.card_name_for_token_id(int(token)) if int(token) > 0 else None
            stats = self.b.loader.get_card(name) if name else None
            if stats is None:
                self.cache[token] = (name, 'none', False)
            else:
                spell = resolve_card_name(name, self.b.loader.load_card_definitions()) in SPELL_REGISTRY
                kind = 'spell' if spell else ('building' if str(getattr(stats, 'card_type', '')).lower() == 'building'
                                              else 'troop')
                self.cache[token] = (name, kind, bool(getattr(stats, 'can_deploy_on_enemy_side', False)))
        return self.cache[token]


def dead(gf):
    """(enemy left dead, enemy right dead, own left dead, own right dead) from global features."""
    return (gf[11] <= 1e-4, gf[12] <= 1e-4, gf[8] <= 1e-4, gf[9] <= 1e-4)


def in_pocket(tile, gf):
    row, col = divmod(tile, 18)
    eld, erd = dead(gf)[:2]
    return 17 <= row <= 20 and ((col < 9 and eld) or (col >= 9 and erd))


def classify(action, hand_kinds, gf):
    if action >= WAIT:
        return 'wait'
    slot, tile = divmod(int(action), 576)
    row, col = divmod(tile, 18)
    if hand_kinds[slot][1] == 'spell':
        return 'spell_enemy' if row >= 16 else 'spell_own'
    if row >= 17:
        return 'pocket' if in_pocket(tile, gf) else 'enemy'
    return 'bridge' if row >= 13 else 'back'


def lane(action, gf):
    """'dead' if the play's column is on the side of a dead enemy princess tower, else 'live'."""
    if action >= WAIT:
        return None
    col = (int(action) % 576) % 18
    eld, erd = dead(gf)[:2]
    return 'dead' if (col < 9 and eld) or (col >= 9 and erd) else 'live'


def view_state(view, builder, kinds):
    obs = view.reserved.packet.observation
    gf = [float(x) for x in obs.global_features]
    threats = 0
    names = builder.token_names
    for i in [int(j) for j in obs.entity_mask.nonzero()[0]]:
        f = obs.entity_features[i]
        tok = int(obs.entity_ids[i])
        if f[3] > .5 and f[1] * 32 < 16 and not (0 <= tok < len(names) and names[tok] in ('Tower', 'KingTower')) \
                and (f[4] > .5 or f[5] > .5):
            threats += 1
    hand = [kinds(int(t)) for t in list(obs.hand_ids)[:4]]
    return gf, hand, threats


def pocket_actions(mask, hand, gf):
    """Pocket-legal troop/building actions in a placement mask."""
    out = []
    for slot in range(4):
        if hand[slot][1] in ('troop', 'building'):
            for tile in range(576):
                if mask[slot * 576 + tile] and in_pocket(tile, gf):
                    out.append(slot * 576 + tile)
    return out


def pick_pocket(pocket, gf, per_slot=3):
    """Up to per_slot pocket tiles per slot nearest to (lane col, row 17), (lane col, row 20), (inner col, row 19)."""
    eld, erd = dead(gf)[:2]
    targets = ([(3, 17), (3, 20), (7, 19)] if eld else []) + ([(14, 17), (14, 20), (10, 19)] if erd else [])
    out = []
    for slot in range(4):
        tiles = [a % 576 for a in pocket if a // 576 == slot]
        if not tiles:
            continue
        chosen = []
        for tx, ty in targets:
            best = min(tiles, key=lambda t: ((t % 18) - tx) ** 2 + ((t // 18) - ty) ** 2)
            if best not in chosen:
                chosen.append(best)
        out += [slot * 576 + t for t in chosen[:per_slot]]
    return out


class Logged:
    """Read-only logging wrapper (plus optional forced action at one tick)."""

    def __init__(self, inner, rt, sink, meta, *, cf_every=0, force=None):
        self.inner, self.rt, self.sink, self.meta = inner, rt, sink, meta
        self.cf_every, self.force = cf_every, force
        self.name, self.deadline_seconds = inner.name, inner.deadline_seconds
        self.kinds = Kinds(rt.R.builder)
        self.search = False
        self.prev_dead = None
        self.forced_applied = False

    def start(self, ctx):
        self.inner.start(ctx)
        self.ctx = ctx
        core = getattr(getattr(self.inner, 'p', None), 'core', None)
        if core is None:
            return
        self.search, self.core = True, core
        self._cand, self._root = None, None
        orig_c, orig_s = core.candidates, core.score_candidates

        def candidates(packet, policy_proposals=()):
            out, mask = orig_c(packet, policy_proposals)
            self._cand = (list(out), mask, set(int(a) for a in policy_proposals),
                          set(getattr(self.inner, '_info', {}).get('first', ())))
            return out, mask

        def score_candidates(root, seat, cands, **kw):
            self._root = (root, seat)
            return orig_s(root, seat, cands, **kw)
        core.candidates, core.score_candidates = candidates, score_candidates

    def close(self):
        self.inner.close()

    def emit(self, row):
        self.sink.write(json.dumps(dict(self.meta, **row)) + '\n')

    def act(self, view):
        if self.search:
            self._cand, self._root = None, None
        d = self.inner.act(view)
        gf, hand, threats = view_state(view, self.rt.R.builder, self.kinds)
        dd = dead(gf)
        towers = [round(x, 4) for x in gf[GF_TOWERS]]
        if dd != self.prev_dead:
            if self.prev_dead is not None:
                self.emit(dict(kind='tower', tick=view.tick, towers=towers, dead=dd))
            self.prev_dead = dd
        if self.search:
            if d.stats is None:
                return d
            if self.force and view.tick == self.force['tick'] and not self.forced_applied:
                from bot.players.base import Decision
                self.emit(dict(kind='forced', tick=view.tick, was=int(d.action), was_wait=d.wait_ticks,
                               action=int(self.force['action'])))
                d = Decision(int(self.force['action']), 0, d.stats)
                self.forced_applied = True
                return d
            self.log_search(view, d, gf, hand, threats, towers, dd)
        elif d.action < WAIT and view.can_act:
            row = dict(kind='play', tick=view.tick, action=int(d.action), cls=classify(d.action, hand, gf),
                       lane=lane(d.action, gf), card=hand[d.action // 576][0], towers=towers, threats=threats,
                       elixir=round(gf[5] * 10, 2))
            if dd[0] or dd[1]:
                from clasher.rl.public_action_mask import PublicActionMaskInput
                mask = self.rt.R.bots['balanced'].mask_builder.build(
                    PublicActionMaskInput.from_confidence_observation(view.reserved.packet))
                row['pocket_legal'] = len(pocket_actions(mask, hand, gf))
            self.emit(row)
        return d

    def log_search(self, view, d, gf, hand, threats, towers, dd):
        a = int(d.action)
        key = {10: 2400, 20: 2401, 40: 2402}.get(d.wait_ticks, a) if a >= WAIT else a
        row = dict(kind='search', tick=view.tick, action=a, wait_ticks=d.wait_ticks, cls=classify(a, hand, gf),
                   lane=lane(a, gf), card=hand[a // 576][0] if a < WAIT else None, towers=towers, threats=threats,
                   elixir=round(gf[5] * 10, 2), hand=[h[0] for h in hand])
        if self._cand is not None:
            cands, mask, props, first = self._cand
            cls = [classify(c, hand, gf) if c < 2400 else 'wait' for c in cands]
            pocket_c = [c for c, k in zip(cands, cls) if k == 'pocket']
            last = self.core.last or {}
            work = list(last.get('candidates') or [])
            scores = dict(zip(work, last.get('scores') or []))
            pw = [c for c in pocket_c if c in work]
            legal = pocket_actions(mask, hand, gf) if (dd[0] or dd[1]) else []
            row.update(n_cand=len(cands), cand_cls={k: cls.count(k) for k in set(cls)}, n_pocket_cand=len(pocket_c),
                       n_pocket_r3a=len([c for c in pocket_c if c in first]), n_pocket_work=len(pw),
                       pocket_legal=len(legal),
                       pocket_legal_cards=sorted({hand[c // 576][0] for c in legal}),
                       chosen_score=scores.get(key), best_pocket_score=max(
                           [scores[c] for c in pw if scores.get(c) is not None], default=None))
            if (self.cf_every and (dd[0] or dd[1]) and row['cls'] != 'pocket' and legal
                    and view.tick % self.cf_every == 0 and self._root is not None):
                row['cf'] = self.counterfactual(key, pick_pocket(legal, gf) + pocket_c[:6], hand, gf)
        self.emit(row)

    def counterfactual(self, chosen, pocket, hand, gf):
        from bot.search.lopp import Learned, batch_rollouts, load_model, mix
        from bot.search.oppmodel import _bonus
        core, (root, seat) = self.core, self._root
        cfg = core.config
        keys = list(dict.fromkeys([WAIT if chosen == 2400 else chosen, WAIT] + list(pocket)))
        elixir = float(core.info.packet.observation.global_features[5]) * 10
        tick = int(core.info.tick)
        out = {}
        for h in HORIZONS:
            b = [core.native.rollout_e1(root, seat, a, 'balanced', core.command_delay, core.opponent_delay, h,
                                        cfg.interval, cfg.elixir_weight, 1e6) for a in keys]
            opp = Learned(load_model('pool'), True, None, 5, seed=[self.ctx.seed, tick])
            L = batch_rollouts(core.native, root, seat, keys, opp, delay=core.command_delay,
                               opp_delay=core.opponent_delay, horizon=h, interval=cfg.interval,
                               elixir_weight=cfg.elixir_weight, tick0=tick)
            out[h] = [round(_bonus(a, mix(bv, lv), elixir), 6) for a, bv, lv in zip(keys, b, L)]
            out[f'b{h}'] = [round(x, 6) for x in b]
            out[f'L{h}'] = [round(x, 6) for x in L]
        return dict(keys=keys, chosen_key=keys[0], cls=[classify(a, hand, gf) for a in keys],
                    cards=[hand[a // 576][0] if a < WAIT else None for a in keys], **{str(k): v for k, v in out.items()})


def worker(wid, jobs, out: Path, base: int, cf_every: int):
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match, x4s_setup
    from bot.eval.headline import make_player
    rt = Runtime()
    fh = open(out / f'games-{wid:03d}.jsonl', 'a')
    dh = open(out / f'dec-{wid:03d}.jsonl', 'a')
    for cand, opp, i, force in jobs:
        case = x4s_setup(rt, i, base)
        t0 = time.time()
        tag = force.get('tag') if force else None
        meta = dict(candidate=cand, opponent=opp, index=i, seat=case['seat'], tag=tag)
        try:
            me = Logged(make_player(rt, cand), rt, dh, meta, cf_every=0 if force else cf_every, force=force)
            players = {case['seat']: me, 1 - case['seat']: make_player(rt, opp)}
            res = play_match(rt, players, seed=case['seed'], decks=case['decks'])
            w = res['winner']
            score = 0.5 if w is None or w == -1 else (1.0 if w == case['seat'] else 0.0)
            row = dict(engine='ours', candidate=cand, opponent=opp, index=i, seat=case['seat'], seed=case['seed'],
                       score=score, winner=w, terminal=res['terminal'], ticks=res['ticks'], towers=res['towers'],
                       plays=res['plays'], accepted=res['accepted'], command_sha256=res['command_sha256'],
                       cpu_seconds=res['cpu_seconds'], wall_seconds=time.time() - t0, tag=tag,
                       force=force, forced_applied=me.forced_applied if force else None)
        except Exception as ex:
            row = dict(candidate=cand, opponent=opp, index=i, seat=case['seat'], tag=tag, error=repr(ex)[:500])
        fh.write(json.dumps(row) + '\n'); fh.flush(); dh.flush()


def done_keys(out: Path):
    keys = set()
    for p in out.glob('games-*.jsonl'):
        for line in p.read_text().splitlines():
            try:
                r = json.loads(line)
                keys.add((r['candidate'], r['opponent'], r['index'], r.get('tag')))
            except Exception:
                pass
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--candidate', default='K4L-R-gs')
    ap.add_argument('--opponents', default='R3a,v1')
    ap.add_argument('--games', type=int, default=300)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--base', type=int, default=None)
    ap.add_argument('--cf-every', type=int, default=0)
    ap.add_argument('--force', type=Path, help='jsonl rows {candidate, opponent, index, tick, action, tag}')
    a = ap.parse_args()
    from bot.eval.headline import HEADLINE_BASE
    base = HEADLINE_BASE if a.base is None else a.base
    a.out.mkdir(parents=True, exist_ok=True)
    done = done_keys(a.out)
    if a.force:
        rows = [json.loads(x) for x in a.force.read_text().splitlines() if x.strip()]
        jobs = [(r['candidate'], r['opponent'], r['index'], r) for r in rows]
    else:
        jobs = [(c, o, i, None) for c in a.candidate.split(',') for o in a.opponents.split(',')
                for i in range(a.start, a.start + a.games)]
    jobs = [j for j in jobs if (j[0], j[1], j[2], j[3].get('tag') if j[3] else None) not in done]
    # search games first (they are ~100x a policy game), interleaved over workers
    jobs.sort(key=lambda j: not j[0].startswith('K4'))
    shares = [jobs[w::a.workers] for w in range(a.workers)]
    (a.out / f'launch-{int(time.time())}.json').write_text(json.dumps(dict(
        args={k: str(v) for k, v in vars(a).items()}, base=base, jobs=len(jobs), started=time.time())))
    procs = [Process(target=worker, args=(w, s, a.out, base, a.cf_every)) for w, s in enumerate(shares) if s]
    for p in procs:
        p.start()
    from bot.eval.headline import reap
    reap(procs)


if __name__ == '__main__':
    main()
