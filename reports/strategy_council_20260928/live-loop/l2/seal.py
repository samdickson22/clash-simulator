"""Content pins for the preregistered local runtime and fixed dependencies."""
import hashlib,json,time
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[3];C=R/'reports/strategy_council_20260928'
files=[p for p in H.glob('*.py') if p.name!='analyze.py']+list(H.glob('*.sh'))+list((H/'runtime').rglob('*.py'))+[H/'PREREG.md',H/'schedule.json',H/'seed-audit.json',R/'gamedata.json']
files+=list((C/'search-tuning').glob('*.py'))+list((C/'search-tuning/native').glob('*.py'))+list((C/'search-tuning/native').glob('*.so'))
files+=list((C/'engine-speed/stage5').glob('*.py'))+[C/'engine-speed/stage5b-r3/deadline_player.py',C/'engine-speed/stage5b-r3/native/clasher_core.abi3.so',C/'engine-speed/es_common.py']
files+=[H.parent/'l1'/p for p in ['calibration.json','v1/model/detector/weights/best.pt','v3/model/last.pt','v3/model/hud.npz','v3/evaluation-validation/selection.json']]
files+=[C/'pilot/v7r4h-launch/runs/s2902/seed-2902/scripted/policy_decisions_001000000.pt']
for p in files:
 if not p.is_file():raise FileNotFoundError(p)
pins={str(p.resolve()):hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in files}
(H/'manifest.json').write_text(json.dumps(dict(created=time.time(),files=pins,protocol='48 paired full matches; no evaluation results before this seal'),indent=2)+'\n')
print('Sealed',len(pins),'files',flush=True)
