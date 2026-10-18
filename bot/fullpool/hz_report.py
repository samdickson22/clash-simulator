"""HZ1 leaf-horizon sweep readout (BOT LEAD 2026-10-17; pre-registered in reports/bot/fullpool/PROGRESS.md).

    python3 -m bot.fullpool.hz_report DIR [DIR ...] [--ref res-wint] [--arms res-H100-wint,...] [--cpu-exclude 127x01]

Rows of bot.livediag.l16_cadence (one bank on every host; duplicate (index, opponent, player) rows must be identical in
command events + outcome and count once, as bot/fullpool/scale_report.py). Per arm: score (per opponent), paired delta
vs --ref with a bootstrap 95% CI (4000 draws, seed 0, resampling cases) pooled and per opponent; enemy play -> our next
searched decision and -> our next play p50/p90 (s); undefended Giant-push share (live_metrics.analyse); CPU-ms per
searched decision (our seat; hosts not in --cpu-exclude); and enemy incursions:
  incursion = a perception frame (our seat's frame, y < 15 = our half) with >= 1 enemy unit on our half after a frame
              with none; elixir_at_cross = our elixir on that frame (mean, median, share >= 8);
              undefended_5s = no accepted play of ours in the 100 ticks after the incursion frame (share).
  wincon_spend_share (BOT LEAD 10-17, s81 review: spending to ~0 before a VISIBLE enemy Hog/Barrel): over enemy
              plays of a win-condition card (WINCON) that the enemy had already played earlier in the battle
              (revealed), the share with an accepted play of ours in the 60 ticks (3 s) before it after which our
              elixir (perception frames, up to the enemy play) fell to <= 1.
  wrong_lane_share (LIVE LEAD play accounting, reports/live/play-accounting/PLAY-ACCOUNTING.md): over our accepted
              non-spell plays with an enemy unit on our half (y < 15) on any perception frame within +-60 ticks
              (+-3 s) of the play ("defensive"), the share whose aimed lane (x < 9 left, else right; centre columns
              8..9 count for both) is opposite the lane of the threat nearest the aimed tile on the frame nearest in
              time to the play that has one. Live: 24-27 %.
  idle_play_share: over our accepted TROOP plays (not SPELLS / BUILDINGS), the share with no enemy unit within 6
              tiles of the play's target tile on the last perception frame at or before the play tick (own frame).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict

from bot.fullpool.scale_report import boot, contrast, fingerprint
from bot.livediag.l16_report import analyse, load, q, reaction, score, to_decision

OWN_HALF = 15
WINDOW = 100
WINCON = {'HogRider', 'GoblinBarrel', 'Giant', 'BattleRam', 'RamRider', 'Balloon', 'Golem', 'RoyalGiant', 'Miner',
          'Graveyard', 'LavaHound', 'ElectroGiant', 'GoblinGiant', 'Pekka', 'MegaKnight', 'RoyalHogs', 'WallBreakers',
          'XBow', 'Mortar', 'GoblinDrill', 'SkeletonBarrel', 'Sparky', 'ThreeMusketeers', 'GiantSkeleton'}
SPELLS = {'Fireball', 'Arrows', 'Zap', 'Log', 'BarbLog', 'Rocket', 'Poison', 'Rage', 'Freeze', 'Lightning', 'Tornado',
          'Earthquake', 'GiantSnowball', 'Clone', 'Mirror', 'Graveyard', 'RoyalDelivery', 'GoblinCurse', 'Void'}
BUILDINGS = {'Cannon', 'InfernoTower', 'Tombstone', 'BombTower', 'GoblinCage', 'GoblinHut', 'Mortar', 'Furnace', 'XBow',
             'Tesla', 'ElixirCollector', 'BarbarianHut', 'GoblinDrill'}


def wincon_spend(r):
    """(events, spent) over revealed enemy win-condition plays (module docstring)."""
    seat = int(r['seat'])
    log = r['result'].get('play_log') or {}
    mine = sorted(t for t, c, a, ok in log.get(str(seat), []) if ok)
    perc = sorted(r.get('packet_perc') or [], key=lambda p: p['tick'])
    seen, ev, spent = set(), 0, 0
    for t, c, a, ok in sorted(log.get(str(1 - seat), [])):
        if not ok:
            continue
        if c in WINCON and c in seen:
            ev += 1
            p0 = next((x for x in mine if t - 60 <= x <= t), None)
            if p0 is not None and any(p['elixir'] is not None and p['elixir'] <= 1.0
                                      for p in perc if p0 <= p['tick'] <= t):
                spent += 1
        seen.add(c)
    return ev, spent


def wrong_lane(r):
    """(defensive plays, wrong-lane ones) (module docstring)."""
    seat = int(r['seat'])
    perc = sorted(r.get('packet_perc') or [], key=lambda p: p['tick'])
    n = wrong = 0
    for t, c, a, ok in (r['result'].get('play_log') or {}).get(str(seat), []):
        if not ok or c in SPELLS or a >= 2304:
            continue
        x, y = (a % 576) % 18 + .5, (a % 576) // 18 + .5
        frames = [p for p in perc if abs(p['tick'] - t) <= 60
                  and any(u.get('owner') == 1 and u['y'] < OWN_HALF for u in p['units'])]
        if not frames:
            continue
        f = min(frames, key=lambda p: abs(p['tick'] - t))
        th = min((u for u in f['units'] if u.get('owner') == 1 and u['y'] < OWN_HALF),
                 key=lambda u: (u['x'] - x) ** 2 + (u['y'] - y) ** 2)
        n += 1
        same = 8 <= x <= 10 or (x < 9) == (th['x'] < 9)
        wrong += not same
    return n, wrong


def idle_plays(r):
    """(troop plays, idle ones) (module docstring)."""
    import bisect
    seat = int(r['seat'])
    perc = sorted(r.get('packet_perc') or [], key=lambda p: p['tick'])
    ticks = [p['tick'] for p in perc]
    n = idle = 0
    for t, c, a, ok in (r['result'].get('play_log') or {}).get(str(seat), []):
        if not ok or c in SPELLS or c in BUILDINGS or a >= 2304:
            continue
        i = bisect.bisect_right(ticks, t) - 1
        if i < 0:
            continue
        x, y = (a % 576) % 18 + .5, (a % 576) // 18 + .5
        n += 1
        idle += not any(u.get('owner') == 1 and (u['x'] - x) ** 2 + (u['y'] - y) ** 2 <= 36 for u in perc[i]['units'])
    return n, idle


def incursions(r):
    seat = int(r['seat'])
    mine = sorted(t for t, c, a, ok in (r['result'].get('play_log') or {}).get(str(seat), []) if ok)
    out, prev = [], False
    for p in sorted(r.get('packet_perc') or [], key=lambda p: p['tick']):
        on = any(u.get('owner') == 1 and u['y'] < OWN_HALF for u in p['units'])
        if on and not prev:
            t = p['tick']
            out.append((p.get('elixir'), not any(t <= x <= t + WINDOW for x in mine)))
        prev = on
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--ref', default='res-wint')
    ap.add_argument('--arms', default='res-H100-wint,res-H240-wint,res-H320-wint')
    ap.add_argument('--gate', default='res-H240-wint')
    ap.add_argument('--gate-opponent', default='LIVE-K4CW-r16-fp')
    ap.add_argument('--cpu-exclude', default='127x01')
    ap.add_argument('--exclude-opp-card', default='', help='drop every case (all arms) whose opponent deck has one of '
                    'these cards, e.g. GoblinHut (sensitivity row: its SpearGoblin_Dummy bodies are unmapped in our view)')
    ap.add_argument('--json')
    a = ap.parse_args(argv)
    excl = {h for h in a.cpu_exclude.split(',') if h}
    drop_cards = {c for c in a.exclude_opp_card.split(',') if c}
    by = defaultdict(dict)
    rows = load(a.dirs)
    dup = same = errors = 0
    for r in rows:
        if r.get('error') or 'result' not in r:
            errors += 1
            continue
        if drop_cards & set(r.get('opponent_deck') or ()):
            continue
        k = (r['index'], r['opponent'])
        old = by[r['player']].get(k)
        if old is not None:
            dup += 1
            same += fingerprint(old) == fingerprint(r)
            if r.get('host', '').split('.')[0] in excl:
                continue
        by[r['player']][k] = r
    if dup != same:
        raise SystemExit(f'{dup - same} of {dup} duplicate rows differ in command events / outcome')
    opps = sorted({k[1] for v in by.values() for k in v})
    out = dict(rows=len(rows), errors=errors, excluded_opp_cards=sorted(drop_cards),
               rows_with_issues=sum(bool(r.get('issues')) for r in rows), duplicates=dup, duplicates_identical=same,
               n_per_player={p: len(v) for p, v in sorted(by.items())}, opponents=opps, arms={}, mechanism={})
    for p, cases in sorted(by.items()):
        todec, react, nodef, pushes, inc = [], [], 0, 0, []
        wev = wsp = tp = tidle = dn = dw = 0
        per_game, cpu_tot, dec_tot = [], 0., 0
        for r in cases.values():
            todec += to_decision(r)
            react += [t for t, _ in reaction(r)]
            m = analyse(r.get('packet_perc') or [], r.get('packet_dec') or [], {})
            pushes += len(m['giant_pushes']); nodef += sum(x['no_def_before_contact'] for x in m['giant_pushes'])
            inc += incursions(r)
            e_, s_ = wincon_spend(r); wev += e_; wsp += s_
            n_, i_ = idle_plays(r); tp += n_; tidle += i_
            n_, w_ = wrong_lane(r); dn += n_; dw += w_
            if r.get('host', '').split('.')[0] not in excl:
                t = (r['result'].get('timing') or {}).get(str(r['seat'])) or {}
                if t.get('decisions'):
                    per_game.append(1000 * t['cpu'] / t['decisions']); cpu_tot += t['cpu']; dec_tot += t['decisions']
        el = [e for e, _ in inc if e is not None]
        out['mechanism'][p] = dict(
            n=len(cases), score=round(sum(score(r) for r in cases.values()) / len(cases), 3),
            score_by_opponent={o: round(sum(score(r) for k, r in cases.items() if k[1] == o)
                                        / max(1, sum(1 for k in cases if k[1] == o)), 3) for o in opps},
            enemy_to_decision_p50=q(todec, .5), enemy_to_decision_p90=q(todec, .9),
            enemy_to_our_play_p50=q(react, .5), enemy_to_our_play_p90=q(react, .9),
            giant_undefended=round(nodef / max(1, pushes), 3), giant_pushes=pushes,
            incursions_per_game=round(len(inc) / len(cases), 2),
            elixir_at_cross_mean=round(sum(el) / len(el), 2) if el else None,
            elixir_at_cross_median=round(statistics.median(el), 2) if el else None,
            elixir_at_cross_ge8=round(sum(e >= 8 for e in el) / len(el), 3) if el else None,
            incursion_undefended_5s=round(sum(u for _, u in inc) / max(1, len(inc)), 3),
            wincon_events=wev, wincon_spend_share=round(wsp / max(1, wev), 3),
            troop_plays=tp, idle_play_share=round(tidle / max(1, tp), 3),
            defensive_plays=dn, wrong_lane_share=round(dw / max(1, dn), 3),
            cpu_ms_per_decision_median=q(per_game, .5),
            cpu_ms_per_decision_pooled=round(1000 * cpu_tot / dec_tot, 1) if dec_tot else None,
            cpu_games=len(per_game), decisions_per_game=round(dec_tot / max(1, len(per_game)), 1))
    for arm in a.arms.split(','):
        out['arms'][arm] = dict(pooled=contrast(by, arm, a.ref), **{o: contrast(by, arm, a.ref, o) for o in opps})
    g = out['arms'].get(a.gate, {}).get(a.gate_opponent, {})
    out['prediction'] = dict(rule=f'{a.gate} - {a.ref} > 0 vs {a.gate_opponent}', delta=g.get('delta'), ci=g.get('ci'),
                             holds=bool(g.get('delta') is not None and g['delta'] > 0))
    text = json.dumps(out, indent=1)
    if a.json:
        open(a.json, 'w').write(text + '\n')
    print(text)


if __name__ == '__main__':
    main(sys.argv[1:])
