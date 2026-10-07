"""Hub-only freeze after explicit preflight. Refuses to replace an existing seal."""
from pathlib import Path
import hashlib,json,time
HERE=Path(__file__).resolve().parent
assert not (HERE/'evaluation-manifest.json').exists()
pre=json.loads((HERE/'preflight.json').read_text());assert pre['passed']
audit=json.loads((HERE/'seed-audit.json').read_text());assert audit['passed']
assert json.loads((HERE/'budget.json').read_text())['candidate_style_rollouts']==63
expected='830fcc54cee623da0e9db021d943a7043474f08faa8e677e21d360c266b962fd'
assert hashlib.sha256((HERE/'runtime/support/clasher_core.abi3.so').read_bytes()).hexdigest()==expected
files={}
for p in HERE.rglob('*'):
    if not p.is_file() or '__pycache__' in p.parts:continue
    rel=str(p.relative_to(HERE))
    if rel.startswith(('runtime/','inputs/')) or p.parent==HERE and (p.suffix=='.py' or p.name in ['PREREG.md','schedule.json','budget.json','noise-model.json','latency.json','execution.json','source-copies.json','seed-audit.json','preflight.json']):
        files[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
(HERE/'evaluation-manifest.json').write_text(json.dumps(dict(sealed_unix=time.time(),files=files),indent=2)+'\n')
print(hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest())
