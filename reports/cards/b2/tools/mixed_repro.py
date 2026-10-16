"""Re-run chosen native-diff mixed-deck games (reports/cards/native-diff/mixed_games.py run_one, unchanged) on the
engine under test. Usage (cwd = a root with engine-rs/src; PYTHONPATH = native:engine-rs:src:<r1>/reports/strategy_council_20260928/engine-speed):
mixed_repro.py ND_DIR OUT.json GAME_ID ...   Prints status / first mismatch tick per game."""
import json, sys
from pathlib import Path
nd = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(nd))
import mixed_games as M
import differential as D
plan = json.loads((nd / 'plan.json').read_text())
games = {g['game']: g for g in plan['games']}
cfg = D.config(tuple(sorted(plan['kinds'])))
res = []
for gid in map(int, sys.argv[3:]):
    r = M.run_one(games[gid], cfg, plan)
    # Keep diagnostics.py detail/phase_step evidence alongside the compact summary.
    Path(sys.argv[2]).with_name(Path(sys.argv[2]).stem + f"-game-{gid}.json").write_text(json.dumps(r, indent=1))
    first = r.get('first') or {}
    row = dict(game=gid, status=r['status'], ticks=r.get('ticks'), first_kind=first.get('kind'), first_tick=first.get('tick'),
               error=(r.get('error') or '')[-300:])
    res.append(row); print(json.dumps(row), flush=True)
json.dump(res, open(sys.argv[2], 'w'), indent=1)
