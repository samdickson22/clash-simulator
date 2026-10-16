"""Pocket moments: stretches after we destroyed an opponent princess tower, and what the bot played in them.

  python pocket.py RUNS_ROOT --out reports/live/loop/pocket-moments.jsonl [--summary]

RUNS_ROOT/<run>/{frames,decisions,events}.jsonl from drive.py (05: /mpac/sdicks02/scratch/live-loop/runs). A tower
counts as destroyed at the first processed frame where the driver's tower record shows it dead and it stays dead to
the end. The stretch runs from that tick to the next opponent tower death or the end of the battle. Plays are split by
the bot's target row (action = slot*576 + row*18 + col; rows 0..14 our side, 15..16 bridge/river, >= 17 enemy side);
'pocket' = enemy side within 5 tiles of the dead tower's x on that lane.
"""
import argparse
import json
from pathlib import Path

SIDE_X = {'l': 3.5, 'r': 14.5}


def load(p):
    return [json.loads(l) for l in open(p)] if Path(p).exists() else []


def run_moments(d):
    F = [f for f in load(d/'frames.jsonl') if f.get('towers')]
    D = [x for x in load(d/'decisions.jsonl') if x.get('submitted')]
    if not F:
        return []
    end_tick = F[-1].get('tick')
    deaths = {}
    for side in 'lr':
        alive = [(f['tick'], any(t[0] == 1 and t[1] == 'p' and t[2] == side and t[3] for t in f['towers'])) for f in F]
        dead_from = None
        for tick, a in alive:
            if a:
                dead_from = None
            elif dead_from is None:
                dead_from = tick
        if dead_from is not None:
            deaths[side] = dead_from
    out = []
    order = sorted(deaths.items(), key=lambda kv: kv[1])
    for i, (side, t0) in enumerate(order):
        t1 = order[i+1][1] if i + 1 < len(order) else end_tick
        if t1 - t0 < 40:                        # < 2 s: the battle ended (king / last tower), no decision window
            continue
        plays = []
        for x in D:
            if not (t0 <= x['tick'] < t1):
                continue
            row, col = (x['action'] % 576)//18, x['action'] % 18
            zone = 'enemy' if row >= 17 else ('bridge' if row >= 15 else 'own')
            pocket = zone == 'enemy' and abs(col + .5 - SIDE_X[side]) <= 5
            plays.append(dict(tick=round(x['tick']), card=x.get('card'), row=row, col=col, zone=zone, pocket=pocket,
                              source=(x.get('stats') or {}).get('source')))
        out.append(dict(run=d.name, tower=f'opp-{side}', tick_range=[round(t0), round(t1)],
                        seconds=round((t1 - t0)/20, 1), plays=len(plays),
                        pocket_plays=sum(p['pocket'] for p in plays), enemy_side=sum(p['zone'] == 'enemy' for p in plays),
                        own_side=sum(p['zone'] == 'own' for p in plays), bot_plays=plays,
                        perception_log=(d/'perception.jsonl').exists()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('--out', required=True)
    ap.add_argument('--invalid', default='s2-m02,s4-m01',
                    help='runs whose tower reads were broken (10-16 dim-screen incident): rows kept, flagged invalid')
    a = ap.parse_args()
    bad = set(a.invalid.split(','))
    rows = []
    for d in sorted(Path(a.root).iterdir()):
        if (d/'decisions.jsonl').exists():
            rows += [dict(r, invalid=d.name in bad) for r in run_moments(d)]
    with open(a.out, 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    for r in rows:
        print(r['run'], r['tower'], r['tick_range'], f"{r['seconds']}s plays {r['plays']} pocket {r['pocket_plays']} "
              f"enemy {r['enemy_side']} own {r['own_side']}")


if __name__ == '__main__':
    main()
