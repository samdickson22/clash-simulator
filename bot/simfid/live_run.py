"""LIVE-recording engine fidelity: quiet-start segments of real games replayed in our engine (simfid, exploration).

    PYTHONPATH=<engine src>:<repo> CLASHER_ROOT=<gamedata root> [SIMFID_CROWN_FROM_GAMEDATA=Fireball,Poison] \
      python -m bot.simfid.live_run --out OUT [--workers 32] [--games N] [--offset K] [--horizon 400]
    python -m bot.simfid.live_run --aggregate OUT [--compare OUT2]

Segments. For every play (either side) whose latest preceding public record shows a QUIET board (towers only), a
segment starts at that record (t0) and runs for --horizon ticks (default 400 = 20 s), cut at the game end or the
first record gap > 30 ticks. All plays in (t0, t0 + horizon] are injected at tick + --offset (own: landing tick;
opponent: midpoint of the first-sighting sample interval / carrier first sighting - 1). Scored on every truth record
in the window, at 5 / 10 / 20 s cumulative horizons.

Truth = the public record (body card + class, owner, position, hp fraction; tower hp fractions). Pairing: per truth
record, units are grouped by (owner, creating card, main body?) (main = a class seen at that card's fresh
deployments, live_data.main_classes; in the engine, a body deploy_card put down itself); within a group, optimal
assignment by distance. A unit-tick is one pair or one unmatched unit:
  pos<=1/4: both alive within 0.25 tile; pos<=1: within 1 tile; hp<=2%: both alive with |hp fraction diff|<=0.02.
Towers: absolute HP error (level max HP x fraction) per tower at the horizon end; tower damage dealt in the window
(truth vs engine) per side; tower-death agreement. Deaths: per (owner, card) group, number of units that died
(alive count drop) within the window, truth vs engine.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
import traceback
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from bot.simfid import live_data as LD

HORIZONS = (100, 200, 400)
TOWER_KEYS = [(o, 'king', None) for o in (0, 1)] + [(o, 'princess', s) for o in (0, 1) for s in ('left', 'right')]
MAINS = None
PROBES = None


def _quiet(rec):
    return not rec.units


def segments(game, horizon):
    recs = game.records
    ticks = [r.tick for r in recs]
    out = []
    used = set()
    for p in game.plays:
        i = int(np.searchsorted(ticks, p.tick - 3)) - 1   # latest record strictly before the play (with slack)
        if i < 0 or i in used or not _quiet(recs[i]):
            continue
        if any(not alive for (_, alive) in recs[i].towers.values()) and False:
            continue
        used.add(i)
        t0 = recs[i].tick
        end = min(t0 + horizon, game.end_tick)
        j = i
        while j + 1 < len(recs) and recs[j + 1].tick <= end:
            if recs[j + 1].tick - recs[j].tick > LD.TICK_GAP:
                end = recs[j].tick
                break
            j += 1
        if end - t0 < 60:
            continue
        plays = [q for q in game.plays if t0 < q.tick <= end]
        flags = []
        if any(q.side == 1 and q.card in game.form_cards for q in plays):
            flags.append('opp_form')
        if any(t0 <= t < end for t in game.dropouts):
            flags.append('dropout')
        if not all(q.certain for q in plays):
            flags.append('uncertain_play')
        out.append(dict(i0=i, t0=t0, end=end, plays=plays, flags=flags))
    return out


# -- levels --------------------------------------------------------------------------------------------------------
def opponent_levels(game, tower_probe, card_probe, mains):
    fr_k, fr_p = [], []
    for r in game.records:
        for (o, kind, side), (f, alive) in r.towers.items():
            if o == 1 and alive and f is not None:
                (fr_k if kind == 'king' else fr_p).append(f)
    lk, nk, tk = LD.infer_level(fr_k, {L: [v['king']] for L, v in tower_probe.items()})
    lp, np_, tp = LD.infer_level(fr_p, {L: [v['princess']] for L, v in tower_probe.items()})
    notes = dict(king=(lk, nk, tk), princess=(lp, np_, tp))
    tower = lp or lk
    if lk and lp and lk != lp:
        notes['tower_conflict'] = True
    # own towers: sanity check of the method (must be 9)
    own_k = [f for r in game.records for (o, kind, s), (f, a) in r.towers.items() if o == 0 and kind == 'king' and a]
    notes['own_king'] = LD.infer_level(own_k, {L: [v['king']] for L, v in tower_probe.items()})
    cards = sorted({p.card for p in game.plays if p.side == 1})
    lv, how = {}, {}
    for c in cards:
        main = set(mains.get(c) or [])
        fr = [u.hp for r in game.records for u in r.units if u.owner == 1 and u.card == c and (not main or u.cls in main)]
        probe = card_probe.get(c) or {}
        L, n, t = LD.infer_level(fr, {k: v for k, v in probe.items() if v}) if probe else (None, 0, 0)
        lv[c], how[c] = L, ('hp' if L else 'none', n, t)
    known = sorted(v for v in lv.values() if v)
    fallback = known[len(known) // 2] if known else (tower or 11)
    for c in cards:
        if lv[c] is None:
            lv[c] = fallback
    notes['cards'] = how
    return lv, (tower or 11), notes


def own_level_check(game, card_probe, mains):
    out = {}
    for c in game.deck:
        main = set(mains.get(c) or [])
        fr = [u.hp for r in game.records for u in r.units if u.owner == 0 and u.card == c and (not main or u.cls in main)]
        probe = card_probe.get(c) or {}
        out[c] = LD.infer_level(fr, {k: v for k, v in probe.items() if v})[0] if probe else None
    return out


# -- scoring -------------------------------------------------------------------------------------------------------
def _assign(a, b):
    """Optimal assignment (Hungarian for small, greedy beyond) -> list of (i, j, dist)."""
    if not a or not b:
        return []
    A = np.array([(u[0], u[1]) for u in a]); B = np.array([(u[0], u[1]) for u in b])
    D = np.hypot(A[:, None, 0] - B[None, :, 0], A[:, None, 1] - B[None, :, 1])
    try:
        from scipy.optimize import linear_sum_assignment
        r, c = linear_sum_assignment(D)
        return [(i, j, float(D[i, j])) for i, j in zip(r, c)]
    except ImportError:
        out, used_i, used_j = [], set(), set()
        for k in np.argsort(D, axis=None):
            i, j = divmod(int(k), D.shape[1])
            if i in used_i or j in used_j:
                continue
            used_i.add(i); used_j.add(j); out.append((i, j, float(D[i, j])))
        return out


def score_frame(truth_units, sim_units, mains, acc, card_acc):
    groups_t, groups_s = defaultdict(list), defaultdict(list)
    for u in truth_units:
        main = u.card in LD.CARRIED_BODIES or u.cls in set(mains.get(u.card) or [u.cls])
        groups_t[u.owner, u.card, main].append((u.x, u.y, u.hp))
    for (o, card, main, x, y, hp) in sim_units:
        # carried bodies (Goblin Barrel goblins, Graveyard skeletons, ...) are a spell's children in the engine
        groups_s[o, card, main or card in LD.CARRIED_BODIES].append((x, y, hp))
    for key in set(groups_t) | set(groups_s):
        T, S = groups_t.get(key, []), groups_s.get(key, [])
        n = max(len(T), len(S))
        q = c1 = h = 0
        for i, j, d in _assign(T, S):
            q += d <= .25
            c1 += d <= 1.
            ht, hs = T[i][2], S[j][2]
            h += (not math.isnan(ht)) and abs(ht - hs) <= .02
        for a in (acc, card_acc[key[0], key[1]]):
            a['ut'] += n; a['q'] += q; a['c1'] += c1; a['hp'] += h; a['miss'] += n - min(len(T), len(S))


def run_segment(game, seg, offset, tower_probe, card_probe, mains, opp, trace=None):
    from bot.simfid.live_engine import LiveSim
    opp_lv, opp_tower, _ = opp
    sim = LiveSim()
    t0rec = game.records[seg['i0']]
    opp_cards = sorted({p.card for p in game.plays if p.side == 1})
    filler = [c for c in ('Knight', 'Archers', 'Arrows', 'Giant', 'Valkyrie', 'Minions', 'Bomber', 'Goblins')
              if c not in opp_cards]
    opp_deck = (opp_cards + filler)[:max(8, len(opp_cards))]
    lv = {c: opp_lv.get(c, opp_tower) for c in opp_deck}
    sim.start(game, t0rec, opp_deck, lv, opp_tower)
    plays = sorted(seg['plays'], key=lambda p: (p.tick + offset, p.side))
    pending = []
    pi = 0
    truth = [r for r in game.records if seg['t0'] < r.tick <= seg['end']]
    ti = 0
    acc = {h: Counter() for h in HORIZONS}
    cards = {h: defaultdict(Counter) for h in HORIZONS}
    tower_truth0 = t0rec.towers
    tower_at = {}
    alive_counts = {}
    drops = Counter()
    while sim.tick < seg['end'] and ti < len(truth):
        t = sim.tick
        while pi < len(plays) and plays[pi].tick + offset <= t:
            pending.append([plays[pi], 0]); pi += 1
        keep = []
        for item in pending:
            if sim.deploy(item[0]):
                sim.counters['deployed'] += 1
            elif item[1] >= 10:
                sim.counters['deploy_dropped'] += 1
                drops[item[0].side, item[0].card] += 1
            else:
                item[1] += 1; sim.counters['deploy_retried'] += 1; keep.append(item)
        pending = keep
        if sim.over:
            # the engine's battle ended (a crown decided it): score its frozen final state, as bot/fidelity does
            frozen = True
        else:
            before = sim.tick
            sim.step()
            frozen = sim.tick == before
        clock = truth[ti].tick if frozen else sim.tick
        if frozen:
            sim.counters['frozen_frames'] += 1
        while ti < len(truth) and truth[ti].tick <= clock:
            r = truth[ti]; ti += 1
            if r.tick != clock:
                continue
            su, st = sim.units()
            for h in HORIZONS:
                if r.tick - seg['t0'] <= h:
                    score_frame(r.units, su, mains, acc[h], cards[h])
            tower_at[r.tick] = (r.towers, st)
            if trace is not None:
                trace.append(dict(tick=r.tick, truth=[(u.owner, u.card, u.cls, round(u.x, 2), round(u.y, 2),
                                                        round(u.hp, 3)) for u in r.units],
                                  sim=[(o, c, m, round(x, 2), round(y, 2), round(hp, 3)) for (o, c, m, x, y, hp) in su],
                                  towers_truth={str(k): v for k, v in r.towers.items()},
                                  towers_sim={str(k): v for k, v in st.items()}))
            alive_counts[r.tick] = (Counter((u.owner, u.card) for u in r.units),
                                    Counter((o, c) for (o, c, *_rest) in su))
    # towers at each horizon end: last scored frame at or before t0 + h
    towers = {}
    frames = sorted(tower_at)
    for h in HORIZONS:
        fs = [f for f in frames if f - seg['t0'] <= h]
        if not fs:
            continue
        tt, st = tower_at[fs[-1]]
        towers[h] = dict(tick=fs[-1], rows=[])
        for key in TOWER_KEYS:
            ft0 = tower_truth0.get(key, (1., True))
            f0 = ft0[0] if ft0[1] else 0.
            ft = tt.get(key, (None, True))
            fT = (ft[0] if ft[1] else 0.) if ft[0] is not None else None
            towers[h]['rows'].append(dict(key=list(key), t0=f0, truth=fT, sim=st.get(key)))
    return dict(t0=seg['t0'], end=seg['end'], flags=seg['flags'], plays=[(p.side, p.card, p.tick, round(p.x, 2), round(p.y, 2), p.source,
                                                      p.certain) for p in plays],
                acc={h: dict(v) for h, v in acc.items()},
                cards={h: {f'{o}|{c}': dict(v) for (o, c), v in d.items()} for h, d in cards.items()},
                towers=towers, counters=dict(sim.counters), drops={f'{s}|{c}': n for (s, c), n in drops.items()},
                ended_early=sim.over and sim.tick < seg['end'])


def _init(mains_path, probe_path):
    global MAINS, PROBES
    MAINS = json.loads(Path(mains_path).read_text())
    PROBES = json.loads(Path(probe_path).read_text())


def run_game(args):
    gdir, out, offset, horizon = args
    dest = Path(out) / (gdir.replace('/', '-') + '.json')
    if dest.exists():
        return gdir, 'skip'
    try:
        game = LD.load_game(LD.MIRROR / gdir, MAINS)
        tower_probe = {int(k): v for k, v in PROBES['towers'].items()}
        card_probe = {c: {int(k): v for k, v in d.items()} for c, d in PROBES['cards'].items()}
        opp = opponent_levels(game, tower_probe, card_probe, MAINS)
        res = dict(game=gdir, levels=game.levels, own_level_check=own_level_check(game, card_probe, MAINS),
                   opp_levels=opp[0], opp_tower_level=opp[1], level_notes=opp[2], errors=game.errors,
                   n_plays=Counter(f'{p.side}|{p.source}' for p in game.plays), segments=[])
        t = time.time()
        for seg in segments(game, horizon):
            try:
                res['segments'].append(run_segment(game, seg, offset, tower_probe, card_probe, MAINS, opp))
            except Exception as ex:   # noqa: BLE001
                res['segments'].append(dict(t0=seg['t0'], error=repr(ex), tb=traceback.format_exc()[-1500:]))
        res['wall_s'] = time.time() - t
        tmp = dest.with_suffix('.tmp')
        tmp.write_text(json.dumps(res))
        tmp.rename(dest)
        return gdir, f"ok {len(res['segments'])}"
    except Exception as ex:   # noqa: BLE001
        return gdir, f'error {ex!r}'


def build_probes(path, cards):
    from bot.simfid.live_engine import probe_card_max_hp, probe_tower_max_hp
    data = dict(towers=probe_tower_max_hp(), cards={})
    for c in sorted(cards):
        try:
            data['cards'][c] = probe_card_max_hp(c)
        except Exception:   # noqa: BLE001
            data['cards'][c] = {}
    Path(path).write_text(json.dumps(data))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    ap.add_argument('--workers', type=int, default=32)
    ap.add_argument('--games', type=int, default=0)
    ap.add_argument('--every', type=int, default=1)
    ap.add_argument('--offset', type=int, default=0)
    ap.add_argument('--horizon', type=int, default=400)
    ap.add_argument('--mains', default='/mpac/sdicks02/jobs/clasher/simfid-20261020/main-classes.json')
    ap.add_argument('--aggregate')
    ap.add_argument('--compare')
    a = ap.parse_args()
    if a.aggregate:
        from bot.simfid.live_report import report
        report(a.aggregate, a.compare)
        return
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    dirs = [str(d.relative_to(LD.MIRROR)) for d in LD.game_dirs()][::a.every]
    if a.games:
        dirs = dirs[:a.games]
    mains = json.loads(Path(a.mains).read_text())
    probe = out / 'probes.json'
    if not probe.exists():
        cards = set(mains) | set(LD.HOG26) | set(LD.CARRIER_CARD.values())
        build_probes(probe, cards)
    meta = dict(engine=os.environ.get('PYTHONPATH', ''), root=os.environ.get('CLASHER_ROOT', ''),
                crown=os.environ.get('SIMFID_CROWN_FROM_GAMEDATA', ''), offset=a.offset, horizon=a.horizon,
                games=len(dirs), every=a.every)
    (out / 'meta.json').write_text(json.dumps(meta, indent=1))
    with Pool(a.workers, initializer=_init, initargs=(a.mains, str(probe))) as pool:
        for g, status in pool.imap_unordered(run_game, [(d, str(out), a.offset, a.horizon) for d in dirs]):
            print(g, status, flush=True)


if __name__ == '__main__':
    main()
