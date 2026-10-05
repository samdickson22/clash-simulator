import functools, json, sys, time
from pathlib import Path
ES = Path('/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/engine-speed')
OQ = Path('/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/oracle-qualification')
sys.path.insert(0, str(ES / 'srp_reference'))
import oq_lib
from clasher.rl.script_rollout_planner import ScriptRolloutPlanner as SRC
games = sys.argv[1:]
ctx = oq_lib.Context()
out = []
for gid in games:
    rec = json.loads((OQ / 'games/srp_xm_c256' / f'{gid}.json').read_text())
    spec = rec['spec']
    row = {'game': gid, 'recorded': [rec['outcome'], rec['candidate_crowns'], rec['opponent_crowns'], rec['ticks'], rec['planner_calls']]}
    for backend in ('python', 'native'):
        oq_lib.ScriptRolloutPlanner = functools.partial(SRC, backend=backend)
        t = time.process_time(); r = oq_lib.play_game(ctx, spec); cpu = time.process_time() - t
        row[backend] = [r['outcome'], r['candidate_crowns'], r['opponent_crowns'], r['ticks'], r['planner_calls'], round(cpu, 1)]
    print(json.dumps(row), flush=True)
