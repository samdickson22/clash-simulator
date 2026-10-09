"""Compact private-runtime hash proof, before launching game workloads."""
import hashlib
import json
from pathlib import Path
import sys

job=Path(sys.argv[1]);repo=job/'repo'
files={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()
       for p in sorted(repo.rglob('*')) if p.is_file() and p.suffix in ('.py','.json','.toml','.lock','.rs','.sh','.npz')
       and '__pycache__' not in p.parts and 'cache' not in p.parts}
source={str(p.relative_to(job/'native-source-v2')):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((job/'native-source-v2').rglob('*')) if p.is_file() and p.name!='e1-source-manifest.json'}
policy=json.loads((repo/'reports/explore/e1/config.json').read_text())['policy']
checkpoint=Path(policy['checkpoint']);digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
assert digest==policy['checkpoint_sha256']
# Adapter byte identity against the sealed gate(c) files, no shared checkout imports.
adapters={}
for f in ('standalone.py','d1.py','events.py','runtime_dependencies/derived_d1.py','runtime_dependencies/own_cycle.py','runtime_dependencies/sidecar_observer.py'):
    p=repo/'imitation/evaluation'/f;q=Path(policy['snapshot'])/'imitation/evaluation'/f
    assert p.read_bytes()==q.read_bytes(),f
    adapters[f]=hashlib.sha256(p.read_bytes()).hexdigest()
result=dict(freeze_commit='bfb9b107',config_sha256=hashlib.sha256((repo/'reports/explore/e1/config.json').read_bytes()).hexdigest(),
            native_sha256=hashlib.sha256((job/'native-v2/clasher_core.abi3.so').read_bytes()).hexdigest(),
            checkpoint_sha256=digest,gate_adapter_exact=adapters,files=files,native_source=source)
(job/'runtime-pin.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('files','native_source')}))
