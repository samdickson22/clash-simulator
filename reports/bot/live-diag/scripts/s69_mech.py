"""s69 loss streak: mechanism stats per battle and per group (s68 W, s68 L, s69 W, s69 L). Run from the livediag tree."""
import json, sys
from pathlib import Path
from bot.livediag.ab_live import result
from bot.livediag.handsync_cmp import battle, mean
from bot.livediag.live_metrics import analyse, jl

RUNS = Path('/mpac/sdicks02/jobs/clasher/bot-livediag/runs')
rows = []
for d in sorted(RUNS.iterdir()):
    if not (d.name.startswith('s68-m') or d.name.startswith('s69-m')) or 'false' in d.name:
        continue
    b = battle(d)
    m = analyse(jl(d / 'perception.jsonl'), jl(d / 'decisions.jsonl'), dict(sid=d.name))
    react = sorted(b['react'])
    opp_plays = len(b.get('births') if isinstance(b.get('births'), list) else []) or b.get('births')
    rows.append(dict(sid=d.name, res=result(d), arm=json.load(open(d / 'session-config.json')).get('arm'),
                     plays=b['plays'], opp_births=b['births'], pushes=b['pushes'], nodef=b['nodef'],
                     elixir_cross=b['elixir_cross'], react_p50=react[len(react) // 2] if react else None,
                     react_p90=react[int(.9 * len(react))] if react else None,
                     spells={c: m['plays'].get(c, 0) for c in ('Fireball', 'Zap')}, giant=m['plays'].get('Giant', 0),
                     cards=dict(m['plays'])))
for r in rows:
    print(r['sid'], r['res'], r['arm'], 'plays', r['plays'], 'opp', r['opp_births'], 'push', r['pushes'], 'nodef', r['nodef'],
          'exc', [round(e, 1) for e in r['elixir_cross']], 'react', r['react_p50'], r['react_p90'], 'FB/Zap', r['spells'], 'G', r['giant'])
groups = {}
for r in rows:
    groups.setdefault(r['sid'][:3] + ':' + (r['res'] or '?'), []).append(r)
print()
for g, v in sorted(groups.items()):
    pu = sum(x['pushes'] for x in v)
    print(g, 'n', len(v), 'plays/b', round(mean([x['plays'] for x in v]), 1), 'opp births/b', round(mean([x['opp_births'] for x in v]), 1),
          'undef', f"{sum(x['nodef'] for x in v)}/{pu}", 'elixir@cross', round(mean([e for x in v for e in x['elixir_cross']]), 2),
          'react p50', round(mean([x['react_p50'] for x in v if x['react_p50'] is not None]), 2),
          'p90', round(mean([x['react_p90'] for x in v if x['react_p90'] is not None]), 2),
          'Fireball/b', round(mean([x['spells']['Fireball'] for x in v]), 2), 'Zap/b', round(mean([x['spells']['Zap'] for x in v]), 2),
          'Giant/b', round(mean([x['giant'] for x in v]), 2))
json.dump(rows, open(sys.argv[1], 'w'), indent=1, default=str)
