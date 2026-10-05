"""Verify the production native planner flag on complete recorded OQ games."""
import contextlib
import io
import json
from pathlib import Path
import sys

C = Path(__file__).resolve().parent
ES = C.parent
sys.path.insert(0, str(ES))
sys.path.insert(0, str(ES.parent / 'oracle-qualification'))
import broad_identity
import oq_lib
from clasher.rl.script_rollout_planner import ScriptRolloutPlanner


class NativePlanner(ScriptRolloutPlanner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, backend='native')


# Only this process opts in; the OQ file and Python default stay unchanged.
oq_lib.ScriptRolloutPlanner = NativePlanner
ctx = oq_lib.Context()
rows = []
for path in broad_identity.recorded_specs(8):
    rec = json.loads(path.read_text())
    with contextlib.redirect_stdout(io.StringIO()):
        got = oq_lib.play_game(ctx, rec['spec'])
    row = dict(id=rec['id'], expected={k:rec[k] for k in broad_identity.FIELDS}, actual={k:got[k] for k in broad_identity.FIELDS})
    rows.append(row)
    (C/'native_recorded.json').write_text(json.dumps(dict(backend='native', provenance=broad_identity.provenance(), results=rows), indent=2)+'\n')
    assert row['expected'] == row['actual'], row
    print('PASS',len(rows),row['id'],row['actual'],flush=True)
