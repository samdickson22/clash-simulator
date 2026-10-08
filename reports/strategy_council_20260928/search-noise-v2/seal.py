"""Hub-only freeze after explicit preflight. Refuses to replace an existing seal."""
from pathlib import Path
import hashlib,json,time
HERE=Path(__file__).resolve().parent
assert __import__('socket').gethostname().split('.')[0]=='127x01'
assert Path('/mpac/sdicks02/jobs/clasher/hub-ready.json').is_file()
assert not (HERE/'evaluation-manifest.json').exists()
pre=json.loads((HERE/'preflight.json').read_text());assert pre['passed'] and pre['protocol']=='r2'
for rel,want in json.loads((HERE/'r2-preflight-inputs.json').read_text())['files'].items():
    assert hashlib.sha256((HERE/rel).read_bytes()).hexdigest()==want,rel
for rel,want in pre['files'].items():
    assert hashlib.sha256((HERE/rel).read_bytes()).hexdigest()==want,rel
audit=json.loads((HERE/'seed-audit.json').read_text());assert audit['passed']
assert json.loads((HERE/'budget.json').read_text())['candidate_style_rollouts']==63
expected='13e908c5cb235a3d81cd585b12caf6c2e5fa624888ed3a3cc0ede14933a5f309'
assert hashlib.sha256((HERE/'runtime/support/clasher_core.abi3.so').read_bytes()).hexdigest()==expected
files={}
for p in HERE.rglob('*'):
    if not p.is_file() or '__pycache__' in p.parts:continue
    rel=str(p.relative_to(HERE))
    if rel.startswith(('runtime/','inputs/')) or p.parent==HERE and (p.suffix=='.py' or p.name in ['PREREG.md','schedule.json','budget.json','noise-model.json','latency.json','execution.json','source-copies.json','seed-audit.json','preflight.json','r2-preflight-inputs.json','r2-invariants.json']):
        files[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
(HERE/'evaluation-manifest.json').write_text(json.dumps(dict(sealed_unix=time.time(),files=files),indent=2)+'\n')
print(hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest())
