"""Summaries of bot.pocket.diag runs (exploration).

    python -m bot.pocket.analyze stats DIR...            pocket-play stats after the candidate takes the first tower
    python -m bot.pocket.analyze cf DIR...               search counterfactual (forced pocket re-scored on the root)
    python -m bot.pocket.analyze pick DIR... --n 150 --out FILE [--h 320]   forced-replay job list
    python -m bot.pocket.analyze forced DIR...           forced replays vs their baseline games (true outcomes)
"""
from __future__ import annotations

import argparse
import json
import random
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

PLAY_CLASSES = ('pocket', 'enemy', 'bridge', 'back', 'spell_enemy', 'spell_own')


def load(dirs):
    games, decs = {}, defaultdict(list)
    for d in dirs:
        for p in sorted(Path(d).glob('games-*.jsonl')):
            for line in p.read_text().splitlines():
                r = json.loads(line)
                games[r['candidate'], r['opponent'], r['index'], r.get('tag')] = r
        for p in sorted(Path(d).glob('dec-*.jsonl')):
            for line in p.read_text().splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                decs[r['candidate'], r['opponent'], r['index'], r.get('tag')].append(r)
    for k in decs:
        # an interrupted game is replayed from scratch on resume: drop its (identical) earlier rows
        uniq = {json.dumps(r, sort_keys=True): r for r in decs[k]}
        decs[k] = sorted(uniq.values(), key=lambda r: (r['tick'], r['kind']))
    return games, decs


def first_tower(rows):
    """(tick, 'cand' | 'opp' | 'both') of the first princess-tower loss, or None."""
    for r in rows:
        if r['kind'] == 'tower':
            e, o = any(r['dead'][:2]), any(r['dead'][2:])
            if e or o:
                return r['tick'], ('both' if e and o else 'cand' if e else 'opp')
    return None


def crowns(g):
    """(candidate crowns, opponent crowns) from the final towers [king, left, right] per seat."""
    def c(t):
        return 3 if t[0] <= 0 else int(t[1] <= 0) + int(t[2] <= 0)
    s = str(g['seat'])
    return c(g['towers'][str(1 - g['seat'])]), c(g['towers'][s])


def pct(n, d):
    return f'{100 * n / d:.1f}%' if d else '–'


def stats(dirs):
    games, decs = load(dirs)
    by = defaultdict(lambda: defaultdict(list))
    for key, rows in decs.items():
        cand, opp, i, tag = key
        if tag is not None:
            continue
        ft = first_tower(rows)
        by[cand, opp]['games'].append(key)
        if not ft or ft[1] != 'cand':
            continue
        t0 = ft[0]
        by[cand, opp]['took'].append(key)
        post = [r for r in rows if r['tick'] >= t0 and r['kind'] in ('search', 'play')]
        # 'ahead' = until the opponent takes a tower back
        back = next((r['tick'] for r in rows if r['kind'] == 'tower' and r['tick'] > t0 and any(r['dead'][2:])), None)
        by[cand, opp]['post'] += [dict(r, dt=r['tick'] - t0, ahead=back is None or r['tick'] < back) for r in post]
        firstp = next((r['tick'] - t0 for r in post if r.get('cls') == 'pocket'), None)
        firstpush = next((r['tick'] - t0 for r in post if r.get('cls') == 'pocket' or
                          (r.get('cls') == 'bridge' and r.get('lane') == 'dead')), None)
        g = games.get(key)
        by[cand, opp]['first'].append((firstp, firstpush, (g or {}).get('ticks', 0) - t0, g))
    out = {}
    for (cand, opp), b in sorted(by.items()):
        post = b['post']
        plays = [r for r in post if r['cls'] != 'wait']
        troop = [r for r in plays if not r['cls'].startswith('spell')]
        cls = Counter(r['cls'] for r in plays)
        dead_bridge = sum(r['cls'] == 'bridge' and r['lane'] == 'dead' for r in plays)
        firsts = b['first']
        tf = [f for f, _, _, _ in firsts if f is not None]
        tpush = [f for _, f, _, _ in firsts if f is not None]
        rem = [r for _, _, r, _ in firsts]
        sc = [g['score'] for *_, g in firsts if g]
        row = dict(games=len(b['games']), took_first=len(b['took']), post_decisions=len(post), post_plays=len(plays),
                   wait_share=round(1 - len(plays) / len(post), 3) if post and cand.startswith('K4') else None,
                   play_shares={k: round(cls[k] / len(plays), 3) for k in PLAY_CLASSES} if plays else {},
                   troop_shares={k: round(cls[k] / len(troop), 3) for k in ('pocket', 'enemy', 'bridge', 'back')}
                   if troop else {},
                   dead_lane_bridge_share=round(dead_bridge / len(plays), 3) if plays else None,
                   back_with_threat=pct(sum(r['cls'] == 'back' and r['threats'] > 0 for r in plays),
                                        cls['back']),
                   plays_per_min=round(len(plays) / max(1, sum(rem)) * 1200, 2),
                   games_with_pocket=len(tf), median_ticks_to_pocket=st.median(tf) if tf else None,
                   games_with_push=len(tpush), median_ticks_to_push=st.median(tpush) if tpush else None,
                   median_remaining_ticks=st.median(rem) if rem else None,
                   score_after_taking_first=round(sum(sc) / len(sc), 3) if sc else None)
        srch = [r for r in post if r['kind'] == 'search' and 'pocket_legal' in r]
        if srch:
            legal = [r for r in srch if r['pocket_legal'] > 0]
            row.update(search_decisions=len(srch), pocket_legal=pct(len(legal), len(srch)),
                       pocket_in_candidates=pct(sum(r['n_pocket_cand'] > 0 for r in legal), len(legal)),
                       pocket_from_r3a=pct(sum(r['n_pocket_r3a'] > 0 for r in legal), len(legal)),
                       pocket_in_work=pct(sum(r['n_pocket_work'] > 0 for r in legal), len(legal)),
                       mean_pocket_candidates=round(sum(r['n_pocket_cand'] for r in legal) / len(legal), 2)
                       if legal else None,
                       wait_when_pocket_legal=pct(sum(r['cls'] == 'wait' for r in legal), len(legal)),
                       pocket_when_pocket_legal=pct(sum(r['cls'] == 'pocket' for r in legal), len(legal)),
                       back_when_pocket_legal=pct(sum(r['cls'] == 'back' for r in legal), len(legal)),
                       chose_pocket_when_in_work=pct(sum(r['cls'] == 'pocket' for r in legal if r['n_pocket_work']),
                                                     sum(r['n_pocket_work'] > 0 for r in legal)),
                       threat_share=pct(sum(r['threats'] > 0 for r in srch), len(srch)))
        pl = [r for r in plays if 'pocket_legal' in r and r['kind'] == 'play']
        if pl:
            row['plays_with_pocket_legal'] = pct(sum(r['pocket_legal'] > 0 for r in pl), len(pl))
        ahead = [r for r in plays if r['ahead']]
        if ahead:
            row['pocket_share_while_ahead'] = round(sum(r['cls'] == 'pocket' for r in ahead) / len(ahead), 3)
        out[f'{cand} vs {opp}'] = row
    return out


def cf_rows(dirs):
    _, decs = load(dirs)
    for key, rows in decs.items():
        for r in rows:
            if r.get('cf'):
                yield key, r


def cf(dirs):
    res = defaultdict(lambda: defaultdict(list))
    for (cand, opp, i, tag), r in cf_rows(dirs):
        c = r['cf']
        pk = [j for j, k in enumerate(c['cls']) if k == 'pocket']
        if not pk:
            continue
        for h in ('160', '320', '480'):
            v = c[h]
            best = max(pk, key=lambda j: v[j])
            res[opp, r['cls'] if r['cls'] != 'wait' else 'wait'][h].append(v[best] - v[0])
            res[opp, 'ALL'][h].append(v[best] - v[0])
            for part in ('b', 'L'):
                vv = c[f'{part}{h}']
                res[opp, 'ALL'][part + h].append(max(vv[j] for j in pk) - vv[0])
    out = {}
    for (opp, cls), d in sorted(res.items()):
        out[f'{opp} {cls}'] = {h: dict(n=len(x), pocket_better=round(sum(y > 1e-9 for y in x) / len(x), 3),
                                       pocket_worse=round(sum(y < -1e-9 for y in x) / len(x), 3),
                                       median_delta_untied=round(st.median([y for y in x if abs(y) > 1e-9] or [0]), 4),
                                       mean_delta=round(sum(x) / len(x), 4))
                               for h, x in d.items()}
    return out


def pick(dirs, n, out, h, seed=0):
    rows = []
    for (cand, opp, i, tag), r in cf_rows(dirs):
        c = r['cf']
        pk = [j for j, k in enumerate(c['cls']) if k == 'pocket']
        # decisions the brief asks about (K4L chose a wait or a defensive own-half play) whose outcome is still open
        # in the scorer's own 160-tick view (not every option a terminal +-2)
        if tag is None and pk and r['cls'] in ('wait', 'back', 'spell_own') and abs(c['160'][0]) < 2:
            best = max(pk, key=lambda j: c[str(h)][j])
            rows.append(dict(candidate=cand, opponent=opp, index=i, tick=r['tick'], action=c['keys'][best],
                             was=r['action'], was_cls=r['cls'], delta=c[str(h)][best] - c[str(h)][0],
                             tag=f'force-{r["tick"]}-{c["keys"][best]}'))
    rng = random.Random(seed)
    sel = []
    for opp in sorted({r['opponent'] for r in rows}):
        pool = [r for r in rows if r['opponent'] == opp]
        # at most one forced decision per game, so outcome deltas are independent across rows
        rng.shuffle(pool)
        seen, take = set(), []
        for r in pool:
            if r['index'] not in seen:
                seen.add(r['index']); take.append(r)
        sel += take[:n]
    Path(out).write_text(''.join(json.dumps(r) + '\n' for r in sel))
    return dict(available=len(rows), selected=len(sel))


def forced(dirs):
    games, _ = load(dirs)
    res = defaultdict(list)
    for (cand, opp, i, tag), g in games.items():
        if tag is None or 'error' in g:
            continue
        base = games.get((cand, opp, i, None))
        if not base or 'error' in base:
            continue
        cf_, cb = crowns(g), crowns(base)
        e, o = str(1 - g['seat']), str(g['seat'])
        hp = lambda x, s: sum(x['towers'][s])
        res[opp].append(dict(ds=g['score'] - base['score'], dcf=cf_[0] - cb[0], dca=cf_[1] - cb[1],
                             dking=(base['towers'][e][0] - g['towers'][e][0]) / 4824,
                             dhp_for=(hp(base, e) - hp(g, e)) / 1000, dhp_against=(hp(base, o) - hp(g, o)) / 1000,
                             applied=g.get('forced_applied'), was_cls=(g.get('force') or {}).get('was_cls'),
                             pred=(g.get('force') or {}).get('delta')))
    out = {}
    for opp, xs in sorted(res.items()) + [('ALL', [x for v in res.values() for x in v])]:
        if not xs:
            continue
        ds = [x['ds'] for x in xs]
        bs = [sum(random.Random(k).choices(ds, k=len(ds))) / len(ds) for k in range(2000)]
        bs.sort()
        out[opp] = dict(n=len(xs), applied=sum(bool(x['applied']) for x in xs), mean_dscore=round(sum(ds) / len(ds), 4),
                        ci95=[round(bs[50], 4), round(bs[1949], 4)],
                        better=sum(d > 0 for d in ds), worse=sum(d < 0 for d in ds),
                        mean_dcrowns_for=round(sum(x['dcf'] for x in xs) / len(xs), 3),
                        mean_dcrowns_against=round(sum(x['dca'] for x in xs) / len(xs), 3),
                        mean_enemy_king_damage_gain=round(sum(x['dking'] for x in xs) / len(xs), 4),
                        mean_enemy_tower_khp_gain=round(sum(x['dhp_for'] for x in xs) / len(xs), 3),
                        mean_own_tower_khp_loss=round(sum(x['dhp_against'] for x in xs) / len(xs), 3))
    return out


def live(dirs):
    """live/loop/pocket.py's definition on sim games: stretch = an enemy princess tower's death (own-frame side l/r)
    to the next enemy princess tower death or the end of the game (skipped if < 40 ticks); plays split by row
    (<= 14 own, 15-16 bridge, >= 17 enemy); pocket = enemy side within 5 tiles of the dead tower's lane x (3.5/14.5).
    Spells count as plays, as in the live script."""
    games, decs = load(dirs)
    agg = defaultdict(lambda: Counter())
    for key, rows in decs.items():
        cand, opp, i, tag = key
        g = games.get(key)
        if tag is not None or not g or 'error' in g:
            continue
        deaths = {}
        for r in rows:
            if r['kind'] == 'tower':
                for j, side in ((0, 'l'), (1, 'r')):
                    if r['dead'][j] and side not in deaths:
                        deaths[side] = r['tick']
        order = sorted(deaths.items(), key=lambda kv: kv[1])
        for n, (side, t0) in enumerate(order):
            t1 = order[n + 1][1] if n + 1 < len(order) else g['ticks']
            if t1 - t0 < 40:
                continue
            c = agg[cand, opp]
            c['stretches'] += 1
            c['seconds'] += (t1 - t0) / 20
            for r in rows:
                if r['kind'] not in ('search', 'play') or not t0 <= r['tick'] < t1 or r['action'] >= 2304:
                    continue
                row, col = (r['action'] % 576) // 18, r['action'] % 18
                zone = 'enemy' if row >= 17 else ('bridge' if row >= 15 else 'own')
                c['plays'] += 1
                c[zone] += 1
                c['pocket'] += zone == 'enemy' and abs(col + .5 - (3.5 if side == 'l' else 14.5)) <= 5
                c['spell'] += r['cls'].startswith('spell')
    out = {}
    for (cand, opp), c in sorted(agg.items()):
        n = c['plays']
        out[f'{cand} vs {opp}'] = dict(stretches=c['stretches'], plays=n, plays_per_min=round(n / max(1, c['seconds']) * 60, 2),
                                       pocket=round(c['pocket'] / n, 3) if n else None,
                                       enemy_side=round(c['enemy'] / n, 3) if n else None,
                                       own_side=round(c['own'] / n, 3) if n else None,
                                       spells=round(c['spell'] / n, 3) if n else None)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['stats', 'cf', 'pick', 'forced', 'live'])
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--n', type=int, default=150)
    ap.add_argument('--h', type=int, default=320)
    ap.add_argument('--out')
    a = ap.parse_args()
    f = dict(stats=stats, cf=cf, forced=forced, live=live)
    res = pick(a.dirs, a.n, a.out, a.h) if a.cmd == 'pick' else f[a.cmd](a.dirs)
    print(json.dumps(res, indent=1, default=str))


if __name__ == '__main__':
    main()
