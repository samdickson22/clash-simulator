"""Live loss analysis s74 (6W-12L) vs s73 (11W-7L), same -res-wint stack (bot lead, live-diag exploration tier).

Read-only on the live run dirs. Pure python3 (no scipy). Per battle:
  outcome      babysitter audit tally (evidence/<sid>-r3/audit-tally.json): result, crowns ours-theirs, trophy delta.
  levels       Battle Log rows (opponent-decks-*-<sid>*.jsonl): opponent card/King levels vs ours; nulls = clipped icons.
  archetype    from the Battle Log deck; when the deck is missing, from the perceived opponent card set (detector raw
               class -> source card via katacr_to_clasher.json, owner 1, >= 2 deploy episodes), marked 'perceived'.
  play         our submitted plays (decisions.jsonl), elixir spent (live/nulls/cards.json costs), Fireball/Zap counts.
  elixir       HUD elixir per frame: time-mean, share of battle time >= 9.0, leaked elixir (time at >= 9.8 x rate:
               1/2.8 s phase 1, 2/2.8 s phases 2-3).
  enemy plays  deploy-episode proxy: an opponent card (owner 1) seen again after >= 3 s unseen, >= 3 detections in
               its first 2 s; plus opponent spell events (score >= 0.6). Committed elixir = sum of their costs.
  reaction     enemy episode -> our next submitted play / next searched decision, seconds (l16_report's definition
               on live rows: enemy play -> our next play).
  pushes       (a) bot.livediag.live_metrics.analyse unchanged (enemy Giant; perception cls), (b) the same rule on
               every opponent win condition by detector source card (tracks must start on the enemy half y >= 15).
               Undefended = no defending play before contact (live_metrics no_def_before_contact).
  -wint        timed waits (stats.timed_wait), interrupted waits (next searched decision before the wait's end),
               the cumulative 'interrupts' counter, waits active when an enemy win condition crossed the river.
  towers       death time of each tower (alive 0 for >= 5 frames, never alive after); deciding crown (the opponent's
               crown that put them ahead for good), its phase, and whether the tower fell from >= 90% HP within
               30 s (one push), plus the opponent units within 6 tiles in the 20 s before it fell.

    PYTHONHASHSEED=0 python3 -m bot.livediag.loss_s74_vs_s73 RUNS EVIDENCE SHARE SRC OUTDIR
  RUNS = scratch/live-loop/runs, EVIDENCE = scratch/live-loop/evidence (babysitter audit tallies), SHARE =
  scratch/live-lead-share (Battle Log jsonl + katacr_to_clasher.json), SRC = a clasher-bot tree (bot.livediag.live_metrics,
  live/nulls/cards.json), OUTDIR gets battles.json + tables.md. Context rows: s69/s70/s72 battles in the 1850 Battle Log.
"""
from __future__ import annotations

import glob
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

TPS = 20.0
WAIT = 2304
OUR_DECK = ('Valkyrie', 'Archers', 'Bats', 'Cannon', 'Fireball', 'Zap', 'MiniPekka', 'Giant')
WINCON = {'Giant', 'HogRider', 'BattleRam', 'RoyalGiant', 'Golem', 'GoblinGiant', 'ElectroGiant', 'Balloon',
          'LavaHound', 'Pekka', 'RamRider', 'RoyalHogs', 'Sparky', 'XBow', 'Mortar', 'WallBreakers', 'Miner',
          'ElixirGolem', 'Bowler', 'MegaKnight', 'GoblinDrill', 'Goblinstein', 'SkeletonKing', 'Prince',
          'DarkPrince', 'Bandit', 'Assassin', 'Ghost', 'RoyalGhost', 'Lumberjack'}
TOWER_X = {'L': 3.5, 'R': 14.5}


def jl(p):
    with open(p) as f:
        return [json.loads(l) for l in f if l.strip()]


def q(xs, f):
    xs = sorted(x for x in xs if x is not None)
    return round(xs[min(len(xs) - 1, int(f * len(xs)))], 2) if xs else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def lane(x):
    return 'L' if x < 9 else 'R'


# --------------------------------------------------------------------------------------------------- archetypes
def archetype(cards):
    s = set(c for c in cards if c)
    if s & {'XBow', 'Mortar'}:
        return 'siege'
    if s & {'LavaHound', 'Balloon'}:
        return 'air-beatdown'
    if 'Pekka' in s:
        return 'pekka-bridge-spam' if s & {'BattleRam', 'HogRider', 'Bandit', 'DarkPrince', 'RamRider', 'Prince'} \
            else 'pekka-control'
    if s & {'Golem', 'GoblinGiant', 'ElectroGiant', 'Giant', 'RoyalGiant', 'ElixirGolem'}:
        return 'giant-beatdown'
    if 'HogRider' in s or 'RoyalHogs' in s or 'RamRider' in s:
        return 'hog-cycle' + ('+barrel' if 'GoblinBarrel' in s else '')
    if 'GoblinBarrel' in s:
        return 'log-bait'
    if 'Graveyard' in s or 'Miner' in s:
        return 'miner/graveyard-control'
    swarm = {'Goblins', 'Skeletons', 'SpearGoblins', 'FireSpirits', 'Bomber', 'ElectroSpirit', 'Bats', 'IceSpirit'}
    if len(s & swarm) >= 5:
        return 'swarm-spam'
    if 'BattleRam' in s:
        return 'ram-bridge-spam'
    return 'control/no-wincon'


# --------------------------------------------------------------------------------------------------- per battle
def battle(rd: Path, costs, kmap, kind):
    perc = jl(rd/'perception.jsonl')
    dec = jl(rd/'decisions.jsonl')
    frames = jl(rd/'frames.jsonl')
    evs = jl(rd/'events.jsonl')
    sess = json.loads((rd/'session.json').read_text())
    out = dict(player=sess.get('player'))
    pby = {p['n']: p for p in perc}
    ticks = [p['tick'] for p in perc]
    t_end = ticks[-1] if ticks else 0
    out['dur_s'] = round(t_end/TPS, 1)
    out['overtime'] = any(p.get('phase') == 3 for p in perc)
    # ---- our plays
    plays = [r for r in dec if r.get('submitted')]
    out['plays'] = len(plays)
    cc = Counter(r.get('card') for r in plays)
    out['cards'] = dict(cc)
    out['fireball'], out['zap'] = cc.get('Fireball', 0), cc.get('Zap', 0)
    out['elixir_spent'] = sum(costs.get(r.get('card'), 0) for r in plays)
    out['elixir_per_min'] = round(out['elixir_spent'] / max(1e-9, t_end/TPS/60), 2)
    # ---- elixir: time-weighted from perception rows (tick-spaced)
    tot = hi9 = leak = 0.0
    el = []
    for a, b in zip(perc, perc[1:]):
        e = a.get('elixir')
        dt = (b['tick'] - a['tick']) / TPS
        if e is None or dt <= 0 or dt > 2:
            continue
        tot += dt
        el.append((e, dt))
        if e >= 9.0:
            hi9 += dt
        if e >= 9.8:
            leak += dt * (1/2.8 if a.get('phase', 1) == 1 else 2/2.8)
    out['elixir_mean'] = round(sum(e*dt for e, dt in el)/tot, 2) if tot else None
    out['elixir_ge9_share'] = round(hi9/tot, 4) if tot else None
    out['elixir_leaked'] = round(leak, 2)
    # ---- opponent detections (detector source card, owner 1)
    det = defaultdict(list)                      # card -> [(tick, x, y)]
    for p in perc:
        for u, raw in zip(p.get('units') or (), p.get('units_yolo') or ()):
            if u.get('owner') != 1:
                continue
            c = (kmap.get(raw) or {}).get('source_card')
            if c:
                det[c].append((p['tick'], u['x'], u['y']))
    episodes = []                                # (tick, card, x, y)
    for c, rows in det.items():
        rows.sort()
        last = -1e9
        for i, r in enumerate(rows):
            if r[0] - last >= 3*TPS:
                n3 = sum(1 for s in rows[i:i+12] if s[0] - r[0] <= 2*TPS)
                if n3 >= 3:
                    episodes.append((r[0], c, r[1], r[2]))
            last = r[0]
    seen_ev = set()
    for p in perc:
        for e in p.get('events') or ():
            if e.get('owner') == 1 and (e.get('score') or 0) >= .6:
                k = (e.get('card'), round(e.get('tick', 0)/1000, 0))
                if k in seen_ev:
                    continue
                seen_ev.add(k)
                episodes.append((p['tick'], e.get('card'), e.get('x'), e.get('y')))
    episodes.sort(key=lambda r: r[0])
    out['enemy_episodes'] = len(episodes)
    out['enemy_elixir_proxy'] = sum(costs.get(c, 0) for _, c, _, _ in episodes)
    out['spend_share'] = round(out['elixir_spent'] / max(1, out['elixir_spent'] + out['enemy_elixir_proxy']), 3)
    ep_by_card = Counter(c for _, c, _, _ in episodes)
    ep_enemy_side = Counter(c for _, c, x, y in episodes if y is not None and y >= 17)
    perceived = sorted(c for c, n in ep_by_card.items()
                       if n >= 2 and (c not in OUR_DECK or ep_enemy_side[c] >= 2) and kind.get(c) != 'tower')
    out['opp_perceived'] = perceived
    # ---- reaction
    ptick = sorted(r['tick'] for r in plays)
    stick = sorted(r['tick'] for r in dec if r.get('stats'))
    import bisect
    rx, rs = [], []
    for t, c, _, _ in episodes:
        if t < 5*TPS:
            continue
        i = bisect.bisect_left(ptick, t)
        if i < len(ptick):
            rx.append((ptick[i] - t)/TPS)
        j = bisect.bisect_left(stick, t)
        if j < len(stick):
            rs.append((stick[j] - t)/TPS)
    out['react_play_p50'], out['react_play_p90'] = q(rx, .5), q(rx, .9)
    out['react_search_p50'], out['react_search_p90'] = q(rs, .5), q(rs, .9)
    out['_react_play'], out['_react_search'] = rx, rs
    # ---- -wint waits / interrupts
    srch = [r for r in dec if r.get('stats') and r['stats'].get('source') == 'search']
    waits = [r for r in srch if r['stats'].get('timed_wait')]
    out['search_decisions'] = len(srch)
    out['search_wait_share'] = round(sum(r['action'] >= WAIT for r in srch)/max(1, len(srch)), 3)
    out['timed_waits'] = len(waits)
    out['timed_wait_mean_s'] = round(sum(r['stats']['timed_wait'] for r in waits)/max(1, len(waits))/TPS, 2)
    out['timed_wait_s_total'] = round(sum(r['stats']['timed_wait'] for r in waits)/TPS, 1)
    inter, wait_windows = 0, []
    for r in waits:
        end = r['tick'] + r['stats']['timed_wait']
        nxt = next((s['tick'] for s in dec if s.get('stats') and s['tick'] > r['tick'] + .5), None)
        cut = nxt is not None and nxt < end - 5
        inter += cut
        wait_windows.append((r['tick'], min(end, nxt) if nxt is not None else end, cut))
    out['waits_interrupted'] = inter
    out['interrupts_counter_max'] = max([r['stats'].get('interrupts', 0) for r in waits] or [0])
    # ---- pushes (generalised live_metrics rule on win conditions)
    pushes = []
    for c, rows in det.items():
        if c not in WINCON:
            continue
        for ln in ('L', 'R'):
            lr = sorted(r for r in rows if lane(r[1]) == ln)
            cur = []
            for r in lr:
                if cur and r[0] - cur[-1][0] > 3*TPS:
                    pushes.append((c, ln, cur)); cur = []
                cur.append(r)
            if cur:
                pushes.append((c, ln, cur))
    prow = []
    for c, ln, rows in sorted(pushes, key=lambda p: p[2][0][0]):
        if len(rows) < 5 or rows[0][2] < 15:
            continue
        cross = next((r for r in rows if r[2] < 15), None)
        if cross is None:
            continue
        contact = next((r for r in rows if r[2] <= 10 and abs(r[1] - TOWER_X[ln]) <= 3), None)
        t0, end = rows[0][0], rows[-1][0]
        first = None
        for r in plays:
            if r['tick'] < t0 - 2*TPS or r['tick'] > end:
                continue
            t = r['action'] % 576
            py, px = t // 18 + .5, t % 18 + .5
            if r.get('card') in ('Fireball', 'Zap'):
                g = min(rows, key=lambda s: abs(s[0] - r['tick']))
                if abs(g[1] - px) <= 3 and abs(g[2] - py) <= 3:
                    first = r; break
            elif py < 15 and (8 <= px <= 9 or lane(px) == ln):
                first = r; break
        tc = contact[0] if contact else None
        pe = min(perc, key=lambda p: abs(p['tick'] - cross[0]))
        in_wait = any(a <= cross[0] < b for a, b, _ in wait_windows)
        prow.append(dict(card=c, lane=ln, t_cross=round(cross[0]/TPS, 1), contact=tc is not None,
                         elixir_cross=pe.get('elixir'), wait_at_cross=in_wait,
                         def_minus_cross_s=round((first['tick'] - cross[0])/TPS, 1) if first else None,
                         undefended=(tc is not None and (first is None or first['tick'] >= tc))))
    out['wincon_pushes'] = len(prow)
    out['wincon_contact'] = sum(p['contact'] for p in prow)
    out['wincon_undefended'] = sum(p['undefended'] for p in prow)
    out['wincon_wait_at_cross'] = sum(p['wait_at_cross'] for p in prow)
    out['elixir_cross_p50'] = q([p['elixir_cross'] for p in prow], .5)
    out['def_minus_cross_p50'] = q([p['def_minus_cross_s'] for p in prow], .5)
    out['_pushes'] = prow
    # ---- towers
    hist = defaultdict(list)                      # (owner, kind, side) -> [(tick, alive, hp, phase, clock)]
    for p in perc:
        for t in p.get('towers') or ():
            hist[(t['owner'], t['kind'], t['side'])].append((p['tick'], t.get('alive'), t.get('hp_read'),
                                                             p.get('phase'), p.get('clock_s')))
    deaths = []
    for k, h in hist.items():
        al = [a for _, a, _, _, _ in h]
        idx = None
        for i in range(len(h)):
            if not any(al[i:]) and len(al) - i >= 5:
                idx = i; break
        if idx is None:
            if len(al) >= 3 and not any(al[-3:]):       # fell in the last frames (king, game over)
                idx = max(i for i in range(len(al)) if al[i]) + 1
            else:
                continue
        t, _, _, ph, clk = h[idx]
        hps = [x[2] for x in h[:idx] if x[2]]
        mx = max(hps[:20]) if hps else None
        full_t = None
        if mx:
            sm = [(h[i][0], sorted(x[2] or 0 for x in h[max(0, i-2):i+3])[2]) for i in range(idx)]
            full_t = max((tt for tt, v in sm if v >= .9*mx), default=None)
        near = Counter()
        tx = 9 if k[1] == 'king' else TOWER_X['L' if k[2] == 'left' else 'R']
        ty = (3 if k[1] == 'king' else 6.5) if k[0] == 0 else (29 if k[1] == 'king' else 25.5)
        for p in perc:
            if t - 20*TPS <= p['tick'] <= t:
                for u, raw in zip(p.get('units') or (), p.get('units_yolo') or ()):
                    if u.get('owner') == 1 - k[0] and abs(u['x'] - tx) <= 6 and abs(u['y'] - ty) <= 6:
                        near[(kmap.get(raw) or {}).get('source_card')] += 1
        deaths.append(dict(owner=k[0], kind=k[1], side=k[2], t=round(t/TPS, 1), phase=ph, clock=round(clk or 0, 1),
                           push_s=round((t - full_t)/TPS, 1) if full_t is not None else None,
                           attackers=[c for c, _ in near.most_common(4)]))
    deaths.sort(key=lambda d: d['t'])
    out['tower_deaths'] = deaths
    for o, nm in ((0, 'our'), (1, 'opp')):
        for kd in ('princess', 'king'):
            v = sorted(x[2] for k, h in hist.items() if k[0] == o and k[1] == kd for x in h[:40] if x[2])
            out[f'{nm}_{kd}_hp0'] = v[len(v)//2] if v else None
    ends = {}
    for o in (0, 1):
        best = None
        for k, h in hist.items():
            if k[0] != o or any(d['owner'] == o and d['kind'] == k[1] and d['side'] == k[2] for d in deaths):
                continue
            hps = [x[2] for x in h if x[2]]
            if not hps:
                continue
            mx = max(hps[:20])
            last = [x for x in h if x[0] >= t_end - 3*TPS and x[2] is not None]
            before = [x for x in h if t_end - 32*TPS <= x[0] <= t_end - 28*TPS and x[2] is not None]
            if not last or not before:
                continue
            drop = (sorted(x[2] for x in before)[len(before)//2] - min(x[2] for x in last)) / mx
            frac30 = sorted(x[2] for x in before)[len(before)//2] / mx
            if best is None or drop > best[0]:
                best = (drop, k, frac30)
        near = Counter()
        if best:
            k = best[1]
            tx = 9 if k[1] == 'king' else TOWER_X['L' if k[2] == 'left' else 'R']
            ty = (3 if k[1] == 'king' else 6.5) if o == 0 else (29 if k[1] == 'king' else 25.5)
            for p in perc:
                if t_end - 20*TPS <= p['tick']:
                    for u, raw in zip(p.get('units') or (), p.get('units_yolo') or ()):
                        if u.get('owner') == 1 - o and abs(u['x'] - tx) <= 6 and abs(u['y'] - ty) <= 6:
                            near[(kmap.get(raw) or {}).get('source_card')] += 1
        ends[o] = dict(owner=o, kind=(best[1][1] if best else '?') + '@end', side=best[1][2] if best else '?',
                       t=out['dur_s'], phase=perc[-1].get('phase') if perc else None,
                       clock=round(perc[-1].get('clock_s') or 0, 1) if perc else None,
                       push_s=30.0 if best and best[2] >= .9 else None,
                       hp_frac_30s_before=round(best[2], 2) if best else None,
                       attackers=[c for c, _ in near.most_common(4)])
    out['_end'] = ends
    return out


def deciding(res, deaths, end=None):
    """The crown that put the winner ahead for good: winner's crown number (loser's final crowns + 1). When that crown
    is not among the detected deaths it fell in the last frames (game-ending king / princess kill; the HUD leaves before
    5 dead frames): `end` (an end-of-battle row) is returned instead."""
    ours, theirs = [d for d in deaths if d['owner'] == 1], [d for d in deaths if d['owner'] == 0]
    if res == 'L':
        k = len(ours) + 1
        return theirs[k-1] if len(theirs) >= k else end
    k = len(theirs) + 1
    return ours[k-1] if len(ours) >= k else end


# --------------------------------------------------------------------------------------------------- stats
def fisher_two_sided(a, b, c, d):
    """2x2 [[a, b], [c, d]] two-sided Fisher exact p (sum of tables with p <= p_obs)."""
    n1, n2, k = a + b, c + d, a + c
    N = n1 + n2
    pmf = lambda x: math.comb(n1, x) * math.comb(n2, k - x) / math.comb(N, k)
    p0 = pmf(a)
    return sum(pmf(x) for x in range(max(0, k - n2), min(k, n1) + 1) if pmf(x) <= p0 * (1 + 1e-9))


def power_fisher(p1, p2, n=18, alpha=.05):
    tot = 0.
    for x in range(n + 1):
        for y in range(n + 1):
            if fisher_two_sided(x, n - x, y, n - y) < alpha:
                tot += math.comb(n, x) * p1**x * (1-p1)**(n-x) * math.comb(n, y) * p2**y * (1-p2)**(n-y)
    return tot


def ranks(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.]*len(xs)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and xs[o[j+1]] == xs[o[i]]:
            j += 1
        for k in range(i, j+1):
            r[o[k]] = (i + j)/2 + 1
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx)/len(rx), sum(ry)/len(ry)
    num = sum((a-mx)*(b-my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a-mx)**2 for a in rx) * sum((b-my)**2 for b in ry))
    return num/den if den else float('nan')


def perm_p(x, y, f, n=20000, seed=0):
    rng = random.Random(seed)
    obs = abs(f(x, y))
    yy = list(y)
    hit = 0
    for _ in range(n):
        rng.shuffle(yy)
        hit += abs(f(x, yy)) >= obs - 1e-12
    return (hit + 1)/(n + 1)


def logistic(x, y, iters=200):
    """1-d logistic regression by Newton; returns (b0, b1, se1)."""
    b0 = b1 = 0.
    for _ in range(iters):
        g0 = g1 = h00 = h01 = h11 = 0.
        for xi, yi in zip(x, y):
            p = 1/(1 + math.exp(-(b0 + b1*xi)))
            w = p*(1-p)
            g0 += yi - p; g1 += (yi - p)*xi
            h00 += w; h01 += w*xi; h11 += w*xi*xi
        det = h00*h11 - h01*h01
        if abs(det) < 1e-12:
            break
        b0 += (h11*g0 - h01*g1)/det
        b1 += (-h01*g0 + h00*g1)/det
    return b0, b1, math.sqrt(h00/det) if det > 0 else float('nan')


def boot_diff(a, b, n=4000, seed=0):
    rng = random.Random(seed)
    a, b = [x for x in a if x is not None], [x for x in b if x is not None]
    if not a or not b:
        return None
    ds = sorted(sum(rng.choice(b) for _ in b)/len(b) - sum(rng.choice(a) for _ in a)/len(a) for _ in range(n))
    return round(ds[int(.025*n)], 3), round(ds[int(.975*n)], 3)


# --------------------------------------------------------------------------------------------------- main
def main(runs, evidence, share, src, outdir):
    runs, evidence, share, src, outdir = map(Path, (runs, evidence, share, src, outdir))
    sys.path.insert(0, str(src))
    from bot.livediag.live_metrics import analyse
    cards = json.loads((outdir/'cards.json' if (outdir/'cards.json').exists() else src/'live/nulls/cards.json').read_text())
    costs = {c['name']: c['cost'] for c in cards}
    kind = {c['name']: c.get('kind') for c in cards}
    kmap = json.loads((share/'katacr_to_clasher.json').read_text())['classes']
    rows = []
    # main sessions (all 18 battles) + pre-wint context battles that have a Battle Log row (s69-s72, King 8 opponents)
    plan = [('s73', [f'm{m:02d}' for m in range(1, 19)], True), ('s74', [f'm{m:02d}' for m in range(1, 19)], True)]
    ctx_bl = {}
    for f in sorted(glob.glob(str(share/'opponent-decks-20261017-1850.jsonl'))):
        for r in jl(f):
            ctx_bl[r['run']] = r
    for sid in ('s69', 's70', 's72'):
        plan.append((sid, sorted(k.split('-')[1] for k in ctx_bl if k.startswith(sid + '-')), False))
    for sid, mms, main_session in plan:
        tally = json.loads((evidence/f'{sid}-r3'/'audit-tally.json').read_text())
        bl = dict(ctx_bl)
        for f in sorted(glob.glob(str(share/f'opponent-decks-*-{sid}*.jsonl'))):
            for r in jl(f):
                bl[r['run']] = r
        for mm in mms:
            rd = runs/sid/mm
            t = tally[mm]
            r = dict(sid=sid, m=mm, main=main_session, result=t['result'], crowns=t['crowns'], delta=t['delta'],
                     trophies=t['trophies'])
            r.update(battle(rd, costs, kmap, kind))
            g = analyse(jl(rd/'perception.jsonl'), jl(rd/'decisions.jsonl'), {})
            gp = g['giant_pushes']
            r['giant_pushes_lm'] = len(gp)
            r['giant_undef_lm'] = sum(p['no_def_before_contact'] for p in gp)
            r['giant_elixir_cross_lm'] = q([p['elixir_cross'] for p in gp], .5)
            b = bl.get(f'{sid}-{mm}')
            if b:
                lv = [x for x in b['opp_levels'] if x is not None]
                ol = [x for x in (b.get('our_levels') or ()) if x is not None]
                r['bl'] = True
                if b.get('crowns') and b.get('result') == r['result']:
                    r['crowns_tally'], r['crowns'] = r['crowns'], f"{b['crowns'][0]}-{b['crowns'][1]}"   # corrected reads
                r['opp_deck'] = b['opp_deck']
                r['opp_levels'] = b['opp_levels']
                r['opp_trophies'] = b.get('opp_trophies')
                r['level_gap'] = round(sum(lv)/len(lv) - sum(ol)/len(ol), 3) if len(lv) >= 6 and ol else None
                r['king_gap'] = (b['opp_king_level'] - b['our_king_level']) \
                    if b.get('opp_king_level') is not None and b.get('our_king_level') is not None else None
                known = [c for c in b['opp_deck'] if c]
                r['archetype'] = archetype(known) if len(known) >= 6 else archetype(r['opp_perceived'])
                r['arch_src'] = 'battle-log' if len(known) >= 6 else 'perceived'
            else:
                r['bl'] = False
                r['level_gap'] = r['king_gap'] = None
                r['archetype'] = archetype(r['opp_perceived'])
                r['arch_src'] = 'perceived'
            deck = [c for c in (r.get('opp_deck') or ()) if c] if r['arch_src'] == 'battle-log' else r['opp_perceived']
            r['pekka'] = 'Pekka' in deck
            dc = deciding(r['result'], r['tower_deaths'], r['_end'][0 if r['result'] == 'L' else 1])
            r['deciding'] = dc
            if r['result'] == 'L' and dc:
                r['decisive_late'] = dc['phase'] in (2, 3)
                r['decisive_one_push'] = dc['push_s'] is not None and dc['push_s'] <= 30
            rows.append(r)
    (outdir/'battles.json').write_text(json.dumps(rows, indent=1, default=str) + '\n')
    report([r for r in rows if r['main']], outdir, [r for r in rows if not r['main']])


def report(rows, outdir, ctx=()):
    L = []
    P = lambda *a: L.append(' '.join(str(x) for x in a))
    by = {s: [r for r in rows if r['sid'] == s] for s in ('s73', 's74')}
    # ---- per-battle table
    P('## Per battle')
    P('| battle | res | crowns | Δtr | dur s | OT | archetype (src) | lvl gap | King gap | plays | elixir/min | '
      'FB | Zap | elixir≥9 share | waits | interrupted | react p50/p90 s | win-con pushes / undefended | '
      'deciding crown (t, phase, push s, attackers) |')
    P('|' + '---|'*19)
    for r in rows:
        d = r['deciding']
        ds = f"{d['kind'][0]}{d['side'][0]} {d['t']}s ph{d['phase']} {d['push_s']}s {'/'.join(map(str, d['attackers'][:3]))}" if d else '-'
        P(f"| {r['sid']}-{r['m']} | {r['result']} | {r['crowns']} | {r['delta']} | {r['dur_s']} | "
          f"{'Y' if r['overtime'] else ''} | {r['archetype']} ({r['arch_src'][0]}) | {r['level_gap']} | {r['king_gap']} | "
          f"{r['plays']} | {r['elixir_per_min']} | {r['fireball']} | {r['zap']} | {r['elixir_ge9_share']} | "
          f"{r['timed_waits']} | {r['waits_interrupted']} | {r['react_play_p50']}/{r['react_play_p90']} | "
          f"{r['wincon_pushes']}/{r['wincon_undefended']} | {ds} |")
    # ---- session aggregates
    P('\n## Session aggregates (mean per battle; pooled reaction quantiles)')
    keys = ['dur_s', 'plays', 'elixir_spent', 'elixir_per_min', 'enemy_elixir_proxy', 'spend_share', 'fireball',
            'zap', 'elixir_mean', 'elixir_ge9_share', 'elixir_leaked', 'search_wait_share', 'timed_waits',
            'timed_wait_mean_s', 'waits_interrupted', 'wincon_pushes', 'wincon_contact', 'wincon_undefended',
            'wincon_wait_at_cross', 'giant_pushes_lm', 'giant_undef_lm', 'elixir_cross_p50', 'def_minus_cross_p50']
    P('| metric | s73 | s74 | s74−s73 95% CI (bootstrap) | s73+s74 wins | s73+s74 losses |')
    P('|---|---|---|---|---|---|')
    allr = rows
    W = [r for r in allr if r['result'] == 'W']
    Lo = [r for r in allr if r['result'] == 'L']
    for k in keys:
        a, b = [r[k] for r in by['s73']], [r[k] for r in by['s74']]
        P(f"| {k} | {mean(a)} | {mean(b)} | {boot_diff(a, b)} | {mean([r[k] for r in W])} | {mean([r[k] for r in Lo])} |")
    for k in ('_react_play', '_react_search'):
        a = [x for r in by['s73'] for x in r[k]]
        b = [x for r in by['s74'] for x in r[k]]
        w = [x for r in W for x in r[k]]
        lo = [x for r in Lo for x in r[k]]
        P(f"| {k[1:]} p50 / p90 (s; n) | {q(a, .5)} / {q(a, .9)} (n={len(a)}) | {q(b, .5)} / {q(b, .9)} (n={len(b)}) | "
          f"| {q(w, .5)} / {q(w, .9)} | {q(lo, .5)} / {q(lo, .9)} |")
    # per-push table pooled
    pp = [dict(p, sid=r['sid'], res=r['result']) for r in allr for p in r['_pushes']]
    P('\n## Win-condition pushes (pooled, by session)')
    for s in ('s73', 's74'):
        x = [p for p in pp if p['sid'] == s]
        P(f"- {s}: pushes {len(x)}, reached contact {sum(p['contact'] for p in x)}, undefended "
          f"{sum(p['undefended'] for p in x)} ({sum(p['undefended'] for p in x)/max(1, sum(p['contact'] for p in x)):.2f} of contacts), "
          f"timed wait active at cross {sum(p['wait_at_cross'] for p in x)}, def−cross p50 {q([p['def_minus_cross_s'] for p in x], .5)} s, "
          f"elixir at cross p50 {q([p['elixir_cross'] for p in x], .5)}; by card {dict(Counter(p['card'] for p in x).most_common(8))}")
    # ---- archetypes
    P('\n## Archetype W/L per session')
    P('| archetype | s73 W-L | s74 W-L |')
    P('|---|---|---|')
    arch = sorted(set(r['archetype'] for r in allr))
    for a in arch:
        f = lambda s: f"{sum(r['result'] == 'W' for r in by[s] if r['archetype'] == a)}-{sum(r['result'] == 'L' for r in by[s] if r['archetype'] == a)}"
        P(f"| {a} | {f('s73')} | {f('s74')} |")
    # ---- levels
    P('\n## King level and tower HP (start-of-battle HP reads, median of the first 40 perception rows)')
    P('| session | battles | opp King (Battle Log) | opp princess HP | opp King HP | our princess / King HP | W-L |')
    P('|---|---|---|---|---|---|---|')
    for s, x in list(by.items()) + [(c, [r for r in ctx if r['sid'] == c]) for c in sorted(set(r['sid'] for r in ctx))]:
        kl = Counter(r['king_gap'] + 7 if r.get('king_gap') is not None else None for r in x)
        P(f"| {s}{'' if s in by else ' (context, Battle Log rows only)'} | {len(x)} | {dict(kl)} | "
          f"{dict(Counter(r['opp_princess_hp0'] for r in x))} | {dict(Counter(r['opp_king_hp0'] for r in x))} | "
          f"{dict(Counter((r['our_princess_hp0'], r['our_king_hp0']) for r in x))} | "
          f"{sum(r['result'] == 'W' for r in x)}-{sum(r['result'] == 'L' for r in x)} |")
    P('\n## Level gap (Battle Log rows with >= 6 opponent levels)')
    lv = [r for r in allr if r.get('level_gap') is not None]
    for s in ('s73', 's74'):
        x = [r for r in lv if r['sid'] == s]
        P(f"- {s}: n={len(x)}, mean card-level gap {mean([r['level_gap'] for r in x])}, King gap mean "
          f"{mean([r['king_gap'] for r in x])}; W {mean([r['level_gap'] for r in x if r['result'] == 'W'])} vs "
          f"L {mean([r['level_gap'] for r in x if r['result'] == 'L'])}")
    if len(lv) >= 6:
        xs = [r['level_gap'] for r in lv]
        ys = [1 if r['result'] == 'W' else 0 for r in lv]
        rho = spearman(xs, ys)
        b0, b1, se = logistic(xs, ys)
        P(f"- pooled n={len(lv)}: Spearman(level gap, win) = {rho:.3f}, permutation p = {perm_p(xs, ys, spearman):.3f}; "
          f"logistic slope {b1:.2f} ± {se:.2f} per level (Wald z {b1/se if se else float('nan'):.2f})")
    # ---- deciding crowns
    P('\n## Losses: deciding crown')
    for s in ('s73', 's74'):
        x = [r for r in by[s] if r['result'] == 'L']
        late = sum(bool(r.get('decisive_late')) for r in x)
        one = sum(bool(r.get('decisive_one_push')) for r in x)
        P(f"- {s}: losses {len(x)}; deciding crown in last 60 s / overtime {late}; deciding tower fell from >= 90% HP "
          f"within 30 s (one push) {one}; three-crown losses {sum(str(r['crowns']).endswith('3') for r in x)}; "
          f"one-crown margin {sum(int(str(r['crowns']).split('-')[1]) - int(str(r['crowns']).split('-')[0]) == 1 for r in x)}")
    # ---- PEKKA split
    P('\n## Opponent deck contains P.E.K.K.A (Battle Log deck; perceived set if clipped)')
    P('| group | s73 W-L | s74 W-L | s69-s72 context W-L (pre-wint, King 8) |')
    P('|---|---|---|---|')
    for flag, nm in ((True, 'PEKKA'), (False, 'no PEKKA')):
        f = lambda xs: f"{sum(r['result'] == 'W' for r in xs if r['pekka'] == flag)}-{sum(r['result'] == 'L' for r in xs if r['pekka'] == flag)}"
        P(f"| {nm} | {f(by['s73'])} | {f(by['s74'])} | {f(ctx)} |")
    pk = [r for r in rows if r['pekka']]
    npk = [r for r in rows if not r['pekka']]
    a, b = sum(r['result'] == 'W' for r in pk), sum(r['result'] == 'W' for r in npk)
    P(f"- s73+s74: PEKKA {a}/{len(pk)} wins vs no-PEKKA {b}/{len(npk)}; Fisher two-sided p = "
      f"{fisher_two_sided(a, len(pk) - a, b, len(npk) - b):.3f} (post-hoc split: treat as a lead, not a finding)")
    c1, c2 = sum(r['pekka'] for r in by['s73']), sum(r['pekka'] for r in by['s74'])
    P(f"- PEKKA opponents: s73 {c1}/18 vs s74 {c2}/18 (Fisher p = {fisher_two_sided(c1, 18 - c1, c2, 18 - c2):.3f})")
    allp = pk + [r for r in ctx if r['pekka']]
    alln = npk + [r for r in ctx if not r['pekka']]
    a2, b2 = sum(r['result'] == 'W' for r in allp), sum(r['result'] == 'W' for r in alln)
    P(f"- with the s69-s72 Battle Log rows: PEKKA {a2}/{len(allp)} vs no-PEKKA {b2}/{len(alln)}; Fisher p = "
      f"{fisher_two_sided(a2, len(allp) - a2, b2, len(alln) - b2):.3f}")
    cw = [r for r in ctx if r['pekka']]
    a3, b3 = sum(r['result'] == 'W' for r in pk), sum(r['result'] == 'W' for r in cw)
    P(f"- PEKKA decks, -res-wint (s73+s74, King 9) {a3}/{len(pk)} vs pre-wint -res/-mk1a1 (s69-s72, King 8) {b3}/{len(cw)}; "
      f"Fisher p = {fisher_two_sided(a3, len(pk) - a3, b3, len(cw) - b3):.3f}")
    nn = [r for r in by['s73'] if not r['pekka']], [r for r in by['s74'] if not r['pekka']]
    w73 = sum(r['result'] == 'W' for r in nn[0]) / len(nn[0])
    wp = a / len(pk)
    exp = c1 * wp + (18 - c1) * sum(r['result'] == 'W' for r in nn[1]) / len(nn[1])
    P(f"- counterfactual: s74 with s73's PEKKA share ({c1}/18) at s74's own per-group win rates -> "
      f"{exp:.1f} expected wins (actual {sum(r['result'] == 'W' for r in by['s74'])}); no-PEKKA win rate s73 {w73:.2f} vs s74 "
      f"{sum(r['result'] == 'W' for r in nn[1]) / len(nn[1]):.2f}")
    P('\n| metric (mean per battle) | PEKKA s73+s74 | no-PEKKA s73+s74 | PEKKA s69-s72 (pre-wint) |')
    P('|---|---|---|---|')
    cpk = [r for r in ctx if r['pekka']]
    for k in ('dur_s', 'plays', 'elixir_per_min', 'spend_share', 'fireball', 'zap', 'timed_waits', 'waits_interrupted',
              'search_wait_share', 'wincon_pushes', 'wincon_contact', 'wincon_undefended', 'elixir_cross_p50'):
        P(f"| {k} | {mean([r[k] for r in pk])} | {mean([r[k] for r in npk])} | {mean([r[k] for r in cpk])} |")
    for k in ('_react_play', '_react_search'):
        f = lambda xs: f"{q([x for r in xs for x in r[k]], .5)} / {q([x for r in xs for x in r[k]], .9)}"
        P(f"| {k[1:]} p50 / p90 s | {f(pk)} | {f(npk)} | {f(cpk)} |")
    for grp, nm in ((pk, 'PEKKA s73+s74'), (npk, 'no-PEKKA s73+s74'), (cpk, 'PEKKA s69-s72')):
        pp = [p for r in grp for p in r['_pushes']]
        P(f"- {nm} win-condition pushes: {len(pp)}, contact {sum(p['contact'] for p in pp)}, undefended "
          f"{sum(p['undefended'] for p in pp)}; by card " +
          ', '.join(f"{c} {sum(1 for p in pp if p['card'] == c)}/{sum(p['undefended'] for p in pp if p['card'] == c)}u"
                    for c, _ in Counter(p['card'] for p in pp).most_common(6)))
    P('\n### Losses to PEKKA decks: deciding crown and the opponent units within 6 tiles of that tower in the 20 s before')
    for r in [r for r in rows + list(ctx) if r['pekka'] and r['result'] == 'L']:
        d = r['deciding'] or {}
        P(f"- {r['sid']}-{r['m']} {r['crowns']} ({r['archetype']}): {d.get('kind')} {d.get('side')} at {d.get('t')} s, phase "
          f"{d.get('phase')}, from >=90% HP within 30 s: {r.get('decisive_one_push')}; attackers {d.get('attackers')}; "
          f"our plays {r['plays']}, MiniPekka {r['cards'].get('MiniPekka', 0)}, Cannon {r['cards'].get('Cannon', 0)}")
    # ---- variance
    a, b = sum(r['result'] == 'W' for r in by['s73']), sum(r['result'] == 'W' for r in by['s74'])
    p = fisher_two_sided(a, 18 - a, b, 18 - b)
    P(f'\n## Variance\n- Fisher exact two-sided {a}/18 vs {b}/18: p = {p:.3f}')
    pooled = (a + b)/36
    for d in (.2, .3, .4, .5):
        lo, hi = pooled - d/2, pooled + d/2
        P(f'- power (alpha .05, 18 vs 18) for true win rates {lo:.2f} vs {hi:.2f} (Δ {d:.2f}): {power_fisher(lo, hi):.2f}')
    (outdir/'tables.md').write_text('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main(*sys.argv[1:6])
