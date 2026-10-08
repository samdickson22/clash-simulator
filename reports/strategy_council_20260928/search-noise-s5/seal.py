"""Light hub seal; every required preflight receipt exists before confirmation."""
from pathlib import Path
import hashlib,json,time,socket
HERE=Path(__file__).resolve().parent
assert socket.gethostname().split('.')[0]=='127x01'
assert not (HERE/'evaluation-manifest.json').exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(HERE/'PREREG.md')==(HERE/'PREREG.sha256').read_text().split()[0]
for host in ('127x04','127x01'):assert json.loads((HERE/f'seed-audit-{host}.json').read_text())['passed']
for i in range(3):
 d=json.loads((HERE/f'equivalence-{i}.json').read_text());assert d['passed'] and len(d['cells'])==4
for i in range(6):
 d=json.loads((HERE/f'pilot-{i}.json').read_text());assert d['terminal'] and 'score' not in d and 'winner' not in d
assert json.loads((HERE/'trace-equivalence.json').read_text())['passed']
assert (HERE/'preflight-status/s5-tests-127x04-r2.exit').read_text().strip()=='0'
assert '\nOK\n' in (HERE/'preflight-status/s5-tests-127x04-r2.log').read_text()
for host in ('127x01','127x04','127x08'):
 audits=list(HERE.glob(f'integrity-{host}-*.json'));assert audits
 d=json.loads(sorted(audits)[-1].read_text());assert not d['s4_tracker_mismatches'] and all(not x['mismatches'] for x in d['studies'].values())
provenance=json.loads((HERE/'runtime-provenance.json').read_text());files=dict(provenance['files'])
for rel,want in files.items():assert sha(HERE/rel)==want,rel
names=[p.name for p in HERE.glob('*.py')]+['PREREG.md','PREREG.sha256','EXECUTION-ENV.md','IMPLEMENTATION-NOTES.md','CONSOLE-POLICY-AMENDMENT.md','console-policy.json','frozen-s4-inputs.json','noise-model.json','latency.json','budget.json','calibration.json','schedule.json','execution.json','seed-audit-127x04.json','seed-audit-127x01.json','runtime-provenance.json','trace-equivalence.json']+[f'pilot-{i}.json' for i in range(6)]+[f'equivalence-{i}.json' for i in range(3)]
for n in names:files[n]=sha(HERE/n)
for p in (HERE/'preflight-status').glob('*'):files[str(p.relative_to(HERE))]=sha(p)
for p in HERE.glob('integrity-*.json'):files[p.name]=sha(p)
(HERE/'evaluation-manifest.json').write_text(json.dumps(dict(study='S5',sealed_unix=time.time(),files=files),indent=2)+'\n')
print(json.dumps(dict(manifest=sha(HERE/'evaluation-manifest.json'),files=len(files))),flush=True)
