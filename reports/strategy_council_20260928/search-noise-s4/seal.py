"""Seal only decomposition code; development v3 cannot change confirmation."""
from pathlib import Path
import hashlib,json,time,socket
HERE=Path(__file__).resolve().parent
assert socket.gethostname().split('.')[0]=='127x01'
assert not (HERE/'evaluation-manifest.json').exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(HERE/'PREREG.md')==(HERE/'PREREG.sha256').read_text().split()[0]
for host in ('127x04','127x01'):assert json.loads((HERE/f'seed-audit-{host}.json').read_text())['passed']
for i in range(3):assert json.loads((HERE/f'equivalence-{i}.json').read_text())['passed']
for i in range(5):
 d=json.loads((HERE/f'pilot-{i}.json').read_text());assert d['terminal'] and 'score' not in d and 'winner' not in d
assert (HERE/'preflight-status/s4-tests-r1.exit').read_text().strip()=='0'
assert '\nOK\n' in (HERE/'preflight-status/s4-tests-r1.log').read_text()
provenance=json.loads((HERE/'runtime-provenance.json').read_text());files=dict(provenance['files'])
for rel,want in files.items():assert sha(HERE/rel)==want,rel
names=['bootstrap.py','player.py','hybrid.py','cells.py','elt.py','noise.py','own_state.py','evaluate.py','trace.py','worker.py','launch_node.py','status.py','collect.py','analyze.py','register.py','seed_audit.py','snapshot_runtime.py','seal.py','preflight.py','test_toggles.py','PREREG.md','PREREG.sha256','noise-model.json','latency.json','budget.json','schedule.json','execution.json','seed-audit-127x04.json','seed-audit-127x01.json','runtime-provenance.json']+[f'pilot-{i}.json' for i in range(5)]+[f'equivalence-{i}.json' for i in range(3)]
for n in names:files[n]=sha(HERE/n)
for p in (HERE/'preflight-status').glob('*'):files[str(p.relative_to(HERE))]=sha(p)
(HERE/'evaluation-manifest.json').write_text(json.dumps(dict(study='S4',sealed_unix=time.time(),files=files),indent=2)+'\n')
print(json.dumps(dict(manifest=sha(HERE/'evaluation-manifest.json'),files=len(files))),flush=True)
