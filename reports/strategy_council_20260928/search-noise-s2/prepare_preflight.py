"""Hash every executable/input before the outcome-suppressed preflight."""
from pathlib import Path
import hashlib,json,time
HERE=Path(__file__).resolve().parent
assert not (HERE/'evaluation-manifest.json').exists()
files={}
for p in HERE.rglob('*'):
    if not p.is_file() or '__pycache__' in p.parts:continue
    rel=str(p.relative_to(HERE))
    if rel.startswith(('runtime/','inputs/','reference/')) or p.parent==HERE and (p.suffix=='.py' or p.name in ('PREREG.md','schedule.json','budget.json','noise-model.json','latency.json','execution.json','s1-source-hashes.json','runtime-provenance.json','seed-audit.json','seed-audit-127x01.json')):
        files[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
p=HERE/'preflight-inputs.json';assert not p.exists()
p.write_text(json.dumps(dict(created_unix=time.time(),files=files),indent=2)+'\n')
print('preflight input files',len(files))
