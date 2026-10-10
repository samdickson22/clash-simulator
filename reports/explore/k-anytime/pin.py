"""Pin owned runtime and sealed v1 adapter against E1 receipt."""
import hashlib,json,subprocess,sys
from pathlib import Path
job=Path(sys.argv[1]);repo=job/'repo';dest=repo/'reports/explore/k-anytime'
reference=json.loads((repo/'reports/explore/e1/receipts/runtime-pin.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
adapters={}
for f,h in reference['gate_adapter_exact'].items():
    p=repo/'imitation/evaluation'/f
    assert sha(p)==h,f
    adapters[f]=h
plan=json.loads((dest/'plan.json').read_text());assert sha(Path(plan['policy']['checkpoint']))==plan['policy']['checkpoint_sha256']
files={str(p.relative_to(repo)):sha(p) for p in sorted(repo.rglob('*')) if p.is_file() and p.suffix in ('.py','.json','.toml','.lock','.rs','.sh','.npz') and '__pycache__' not in p.parts}
source={str(p.relative_to(job/'native-source')):sha(p) for p in sorted((job/'native-source').rglob('*')) if p.is_file()}
result=dict(pinned_at_utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),freeze_commit='0f2a9ec8',plan_sha256=sha(dest/'plan.json'),native_sha256=sha(job/'native/clasher_core.abi3.so'),checkpoint_sha256=plan['policy']['checkpoint_sha256'],gate_adapter_exact=adapters,files=files,native_source=source,native_features=['extension-module','gil-release'],baseline='E1 deployed build46 plus private W-screen8 and tick-cancellable commands; combat source unchanged')
(job/'runtime-pin.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('files','native_source')}))
