"""Light hub seal, only after all preflight evidence passes."""
from pathlib import Path
import hashlib,json,time,re,socket
HERE=Path(__file__).resolve().parent
assert socket.gethostname().split('.')[0]=='127x01'
assert not (HERE/'evaluation-manifest.json').exists()
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((HERE/'preflight-inputs.json').read_text())
for rel,want in inputs['files'].items():assert digest(HERE/rel)==want,rel
for name in ('seed-audit.json','seed-audit-127x01.json'):assert json.loads((HERE/name).read_text())['passed']
assert json.loads((HERE/'budget.json').read_text())['candidate_style_rollouts']==63
assert digest(HERE/'runtime/support/clasher_core.abi3.so')=='13e908c5cb235a3d81cd585b12caf6c2e5fa624888ed3a3cc0ede14933a5f309'
evidence={};cpu=0.
labels=['s2-tests-v1']+[f's2-equivalence-{i}-v1' for i in range(3)]+[f's2-pilot-{i}-v1' for i in range(14)]
for label in labels:
    log=HERE/'preflight-status'/f'{label}.log';rc=HERE/'preflight-status'/f'{label}.exit'
    assert rc.read_text().strip()=='0',label
    evidence[log.name]=digest(log);evidence[rc.name]=digest(rc)
    values=re.findall(r'^\t(?:User time \(seconds\)|System time \(seconds\)):\s*([0-9.]+)',log.read_text(),re.M)
    assert len(values)==2,(label,values);cpu+=sum(map(float,values))
log=(HERE/'preflight-status/s2-tests-v1.log').read_text();assert '\nOK\n' in log
for i in range(3):
    p=HERE/f'equivalence-{i}.json';data=json.loads(p.read_text());assert data['passed'];evidence[p.name]=digest(p)
for i in range(14):
    p=HERE/f'pilot-{i}.json';data=json.loads(p.read_text());assert data['terminal'] and 'score' not in data and 'winner' not in data;evidence[p.name]=digest(p)
pre=dict(passed=True,utc=time.time(),cpu_hours=cpu/3600,evidence=evidence,files=inputs['files'])
(HERE/'preflight.json').write_text(json.dumps(pre,indent=2)+'\n')
files=dict(inputs['files'])
for n in ('preflight.json','preflight-inputs.json'):files[n]=digest(HERE/n)
(HERE/'evaluation-manifest.json').write_text(json.dumps(dict(study='S2',sealed_unix=time.time(),files=files),indent=2)+'\n')
print('manifest',digest(HERE/'evaluation-manifest.json'),'preflight_cpu_hours',cpu/3600)
