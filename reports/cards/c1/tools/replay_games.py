"""Re-run named native-diff mixed games (reports/cards/native-diff/mixed_games.py:run_one) against the native and
Python on PYTHONPATH (no pin assert), for the Batch C1 native-parity fixes. Exploration probe, no engine edits.

Usage (PYTHONPATH = native : engine-rs : src : engine-speed : native-diff dir):
  replay_games.py PLAN.json OUT.json GAME [GAME ...]
Writes {game: {status, ticks, first: {tick, kind, phase...}}}. The config is exported fresh (never a cached one).
"""
import json, sys, time
from pathlib import Path
import differential as D
import mixed_games as M

plan_path, out_path, *games = sys.argv[1:]
plan = json.loads(Path(plan_path).read_text())
cfg = D.config(tuple(sorted(plan['kinds'])))
by_id = {g['game']: g for g in plan['games']}
out = {}
for g in map(int, games):
    t0 = time.time()
    r = M.run_one(by_id[g], cfg, plan)
    first = r.get('first') or {}
    phases = ((r.get('triage') or {}).get('phases'))
    out[g] = dict(status=r['status'], ticks=r['ticks'], first_tick=first.get('tick'), first_kind=first.get('kind'),
                  winner=r.get('winner'), error=r.get('error'), triage_phase=None if not phases else
                  next((k for k, v in phases.items() if v['field_diff']), None),
                  triage_fields=None if not phases else
                  [d['field'] for v in phases.values() for d in v['field_diff']][:8],
                  actions=len(r['actions']), seconds=round(time.time()-t0, 1))
    print(g, out[g], flush=True)
    Path(out_path).write_text(json.dumps(out, indent=1))
