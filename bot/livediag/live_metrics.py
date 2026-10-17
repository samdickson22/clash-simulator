"""Live-gameplay diagnosis metrics on live-loop session logs (bot lead, exploration tier; read-only on the logs).

Frame: perception units and action tiles are both seat-0 arena tiles (x 0..18 from the left, y 0..32 from our king);
our half is y < 15, the river 15..17. Action = slot*576 + row*18 + col, WAIT 2304. 20 ticks per second.

Per session (a copy of runs-all/<sid>):
  tiers      share of logged decisions (stats != None) by source; WAIT share; deadline hits (hit / fallback /
             student_default / preparation_cutoff); search_wall_ms.
  plays      submitted plays by card (the tracker's card for the tapped slot) and whether that card is the perceived
             HUD card in that slot on the decision frame (hand mismatch).
  hand       per perception frame: is Giant / Fireball / Cannon in the perceived hand.
  pushes     enemy Giant tracks per lane (detections <= 3 s apart). cross = first frame on our half (y < 15);
             contact = first frame within reach of our princess tower (y <= 10, |x - tower x| <= 3). Defence = our
             first submitted play with target on our half (troop/building) or a Fireball within 3 tiles of the Giant,
             after the Giant's first detection; lane = same side of x = 9 (centre tiles 8..9 count for both).
  cannon     every Cannon play: target tile, threat lane = side with most enemy ground units on our half
             (y < 16) at the decision frame, same / opposite / none.

    python3 -m bot.livediag.live_metrics RUNS_DIR OUT.json [sid ...]
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

WAIT = 2304
TPS = 20.0
CARDS = ('Valkyrie', 'Archers', 'Minions', 'Cannon', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer')
DECK_S62 = ('Valkyrie', 'Archers', 'Bats', 'Cannon', 'Fireball', 'Zap', 'MiniPekka', 'Giant')   # Sam's live deck from s62
CARDS_ALL = tuple(dict.fromkeys(CARDS + DECK_S62))
SPELLS = ('Fireball', 'Arrows', 'Zap', 'Log', 'Rocket', 'Poison')
AIR = ('Minions', 'MinionHorde', 'BabyDragon', 'Balloon', 'Bats', 'InfernoDragon', 'MegaMinion', 'LavaHound',
       'Minion', 'Bat', 'LavaPup', 'SkeletonDragon', 'ElectroDragon')


def tile(action):
    t = action % 576
    return action // 576, t // 18, t % 18      # slot, row (y), col (x)


def lane(x):
    return 'L' if x < 9 else 'R'


def lane_ok(px, gx):
    return 8 <= px <= 9 or lane(px) == lane(gx)


def jl(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def session(d: Path):
    cfg = json.loads((d/'session-config.json').read_text())
    perc = jl(d/'perception.jsonl')
    dec = jl(d/'decisions.jsonl')
    out = dict(sid=d.name, player=cfg.get('player'), fast=cfg.get('fast'), deck=cfg.get('deck'),
               units=(lambda u: u.get('spec') if isinstance(u, dict) else u)(cfg.get('units_source')) or cfg.get('export'))
    return analyse(perc, dec, out)


def analyse(perc, dec, out):
    """perc: [{n, tick, units [{owner, cls, x, y}], hand {cards}, elixir}] in the seat's own frame; dec: [{n, tick,
    action, submitted, stats, card}] (live decisions.jsonl rows; bot/livediag/sim_diag.py writes the same shape)."""
    pby = {r['n']: r for r in perc}
    out.update(n_perc=len(perc), n_dec=len(dec))
    # ---- tiers
    src, waits, hits = Counter(), Counter(), Counter()
    swall = []
    for r in dec:
        s = r.get('stats')
        if not s:
            src['null'] += 1
            continue
        k = s.get('source')
        src[k] += 1
        if r['action'] >= WAIT:
            waits[k] += 1
        for f in ('hit', 'fallback', 'student_default'):
            if s.get(f):
                hits[f'{k}:{f}'] += 1
        if 'preparation_cutoff' in s:
            hits[f'{k}:prep:{s["preparation_cutoff"]}'] += 1
        if s.get('search_wall_ms') is not None:
            swall.append(s['search_wall_ms'])
    out['source'] = dict(src)
    out['wait_by_source'] = dict(waits)
    out['cut'] = dict(hits)
    swall.sort()
    out['search_wall_ms'] = dict(p50=swall[len(swall)//2], p95=swall[int(.95*len(swall))], max=swall[-1]) if swall else None
    # ---- plays + hand mismatch
    plays = []
    for r in dec:
        if not r.get('submitted'):
            continue
        slot, row, col = tile(r['action'])
        p = pby.get(r['n'])
        hud = (p or {}).get('hand', {}).get('cards') if p else None
        plays.append(dict(n=r['n'], tick=r['tick'], card=r.get('card'), slot=slot, x=col + .5, y=row + .5,
                          source=(r.get('stats') or {}).get('source'), hud=hud,
                          hud_card=hud[slot] if hud and slot < len(hud) else None,
                          elixir=(p or {}).get('elixir'), f2t=r.get('frame_to_tap_ms'), tap=r.get('tap')))
    out['plays'] = Counter(p['card'] for p in plays)
    out['play_sources'] = Counter(p['source'] for p in plays)
    mm = [p for p in plays if p['hud_card'] is not None and p['hud_card'] != p['card']]
    out['hand_mismatch'] = dict(n=len(mm), of=sum(p['hud_card'] is not None for p in plays),
                                pairs=Counter(f"{p['card']}->{p['hud_card']}" for p in mm))
    f2t = sorted(p['f2t'] for p in plays if p['f2t'] is not None)
    out['frame_to_tap_ms'] = dict(p50=f2t[len(f2t)//2], p95=f2t[int(.95*len(f2t))]) if f2t else None
    # ---- hand presence (perceived)
    inhand, nh = Counter(), 0
    for p in perc:
        h = (p.get('hand') or {}).get('cards')
        if not h or p.get('tick', 0) < 90:
            continue
        nh += 1
        for c in set(h):
            inhand[c] += 1
    out['in_hand_frac'] = {c: round(inhand[c]/nh, 3) for c in CARDS_ALL if inhand[c]} if nh else None
    # ---- enemy Giant pushes
    det = defaultdict(list)          # lane -> [(tick, x, y, n)]
    for p in perc:
        for u in p['units']:
            if u.get('owner') == 1 and u.get('cls') == 'Giant':
                det[lane(u['x'])].append((p['tick'], u['x'], u['y'], p['n']))
    pushes = []
    for ln, rows in det.items():
        rows.sort()
        cur = []
        for r in rows:
            if cur and r[0] - cur[-1][0] > 3*TPS:
                pushes.append((ln, cur)); cur = []
            cur.append(r)
        if cur:
            pushes.append((ln, cur))
    tx = {'L': 3.5, 'R': 14.5}
    import bisect
    pt = [p['tick'] for p in perc]
    def near(t):
        i = bisect.bisect_left(pt, t)
        return perc[max(0, min(i, len(perc)-1))]
    elixir_at = lambda t: near(t).get('elixir')
    hand_at = lambda t: (near(t).get('hand') or {}).get('cards')
    prow = []
    for ln, rows in sorted(pushes, key=lambda p: p[1][0][0]):
        t0 = rows[0][0]
        cross = next((r for r in rows if r[2] < 15), None)
        if cross is None or len(rows) < 5:
            continue                  # never perceived on our half (or a flicker)
        contact = next((r for r in rows if r[2] <= 10 and abs(r[1] - tx[ln]) <= 3), None)
        end = rows[-1][0]
        defs = []
        for p in plays:
            if p['tick'] < t0 - 2*TPS or p['tick'] > end:
                continue
            if p['card'] == 'Fireball':
                g = min(rows, key=lambda r: abs(r[0] - p['tick']))
                if abs(g[1] - p['x']) <= 3 and abs(g[2] - p['y']) <= 3:
                    defs.append(p)
            elif p['y'] < 15 and lane_ok(p['x'], cross[1]):
                defs.append(p)
        first = defs[0] if defs else None
        tc = contact[0] if contact else None
        row = dict(lane=ln, t_first=round(t0/TPS, 1), t_cross=round(cross[0]/TPS, 1),
                   t_contact=round(tc/TPS, 1) if tc else None, t_end=round(end/TPS, 1),
                   elixir_cross=elixir_at(cross[0]), hand_cross=hand_at(cross[0]),
                   first_def=dict(card=first['card'], t=round(first['tick']/TPS, 1), x=first['x'], y=first['y'],
                                  source=first['source']) if first else None,
                   def_minus_cross_s=round((first['tick'] - cross[0])/TPS, 1) if first else None,
                   def_before_contact=(first is not None and (tc is None or first['tick'] < tc)),
                   no_def_before_contact=(tc is not None and (first is None or first['tick'] >= tc)),
                   cannon_in_hand_cross='Cannon' in (hand_at(cross[0]) or ()))
        # search WAIT decisions while the Giant was on our half before contact / first defence
        stop = min(x for x in (tc, first['tick'] if first else None, end) if x is not None)
        w = [r for r in dec if r.get('stats') and cross[0] <= r['tick'] <= stop]
        row['decisions_cross_to_def'] = Counter((r['stats'].get('source'), 'WAIT' if r['action'] >= WAIT else 'play')
                                                for r in w)
        row['decisions_cross_to_def'] = {f'{a}:{b}': c for (a, b), c in row['decisions_cross_to_def'].items()}
        prow.append(row)
    out['giant_pushes'] = prow
    # ---- Cannon placements
    cann = []
    for p in plays:
        if p['card'] != 'Cannon':
            continue
        pr = pby.get(p['n']) or {}
        en = [u for u in pr.get('units', ()) if u.get('owner') == 1 and u['y'] < 16 and u.get('cls') not in AIR]
        cnt = Counter(lane(u['x']) for u in en)
        thr = cnt.most_common(1)[0][0] if cnt else None
        rel = 'none' if thr is None else ('centre' if 8 <= p['x'] <= 9 else ('same' if lane(p['x']) == thr else 'opposite'))
        cann.append(dict(t=round(p['tick']/TPS, 1), x=p['x'], y=p['y'], threat=thr, rel=rel,
                         enemies=[(u.get('cls'), round(u['x'], 1), round(u['y'], 1)) for u in en],
                         enemies_far=[(u.get('cls'), round(u['x'], 1), round(u['y'], 1))
                                      for u in pr.get('units', ()) if u.get('owner') == 1 and u['y'] >= 16],
                         source=p['source'], hud_card=p['hud_card']))
    out['cannon'] = cann
    return out


def main(argv):
    runs, dst = Path(argv[0]), Path(argv[1])
    sids = argv[2:] or sorted(p.name for p in runs.iterdir() if (p/'decisions.jsonl').exists())
    res = []
    for sid in sids:
        d = runs/sid
        if not (d/'session-config.json').exists() or (d/'decisions.jsonl').stat().st_size == 0:
            continue
        try:
            res.append(session(d))
        except Exception as ex:      # one broken session must not hide the rest
            res.append(dict(sid=sid, error=repr(ex)[:300]))
    dst.write_text(json.dumps(res, default=lambda o: dict(o) if isinstance(o, Counter) else str(o)) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
