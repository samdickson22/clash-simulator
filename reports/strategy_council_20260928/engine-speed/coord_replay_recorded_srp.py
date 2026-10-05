import json, sys, importlib
from pathlib import Path
harness = Path(sys.argv[1]); gid = sys.argv[2]
sys.path.insert(0, str(harness))
import oq_lib
OQ = Path('/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/oracle-qualification')
rec = json.loads((OQ / 'games/srp_xm_c256' / f'{gid}.json').read_text())
r = oq_lib.play_game(oq_lib.Context(), rec['spec'])
print(json.dumps({'harness': str(harness), 'recorded': [rec['outcome'], rec['candidate_crowns'], rec['opponent_crowns'], rec['ticks'], rec['planner_calls']], 'now': [r['outcome'], r['candidate_crowns'], r['opponent_crowns'], r['ticks'], r['planner_calls']], 'runtime': r.get('runtime')}))
