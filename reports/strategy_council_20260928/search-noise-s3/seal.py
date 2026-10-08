"""Light hub seal after immutable preflight evidence; no outcomes read."""
from pathlib import Path
import hashlib,json,time,socket
HERE=Path(__file__).resolve().parent
assert socket.gethostname().split('.')[0]=='127x01'
assert not (HERE/'evaluation-manifest.json').exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for host in ('127x04','127x01'):assert json.loads((HERE/f'seed-audit-{host}.json').read_text())['passed']
assert json.loads((HERE/'equivalence.json').read_text())['passed']
for i in range(7):
 d=json.loads((HERE/f'pilot-{i}.json').read_text());assert d['terminal'] and 'score' not in d and 'winner' not in d
assert len([r for f in (HERE/'replay-tests').glob('*.json') for r in json.loads(f.read_text())])==24
log=(HERE/'preflight-status/s3-tests-final.log').read_text();assert '\nOK\n' in log
assert (HERE/'preflight-status/s3-tests-final.exit').read_text().strip()=='0'
dev=json.loads((HERE/'dev-summary-v3.json').read_text());assert dev['traces']==56
for c in ('T2-N97','T2-N90','T2-N64'):
 d=dev['cells'][c]['validation'];assert d['coverage']>=.88 and d['post_error_coverage']>=.80 and d['width']<d['legacy']['width'],(c,d)
provenance=json.loads((HERE/'runtime-provenance.json').read_text());files=dict(provenance['files'])
for rel,want in files.items():assert sha(HERE/rel)==want,rel
names=[p.name for p in HERE.glob('*.py')]+['PREREG.md','DESIGN.md','DEV-LOG.md','DEV-RESULTS.md','dev-code-freeze.json','cells.py','noise-model.json','latency.json','budget.json','calibration.json','schedule.json','execution.json','seed-audit-127x04.json','seed-audit-127x01.json','runtime-provenance.json','dev-summary-v3.json','equivalence.json']+[f'pilot-{i}.json' for i in range(7)]
for n in names:files[n]=sha(HERE/n)
for p in (HERE/'replay-tests').glob('*.json'):files[str(p.relative_to(HERE))]=sha(p)
for p in (HERE/'preflight-status').glob('*'):files[str(p.relative_to(HERE))]=sha(p)
(HERE/'evaluation-manifest.json').write_text(json.dumps(dict(study='S3',sealed_unix=time.time(),files=files),indent=2)+'\n')
print(json.dumps(dict(manifest=sha(HERE/'evaluation-manifest.json'),files=len(files))),flush=True)
