from pathlib import Path
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
R=HERE/'runtime'
def copy(p, dest=None):
    p=Path(p);dest=R/(dest or p.relative_to(ROOT));dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(p,dest)
    return str(p),dict(copy=str(dest.relative_to(HERE)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
files={}
for p in (ROOT/'src/clasher').rglob('*'):
    if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.json','.csv'):
        k,v=copy(p);files[k]=v
for p in (ROOT/'engine-rs').glob('*.py'):
    k,v=copy(p);files[k]=v
for rel in ['gamedata.json','pyproject.toml','reports/strategy_council_20260928/engine-speed/es_common.py','reports/strategy_council_20260928/m0/data/roles_v2/training.json']:
    k,v=copy(ROOT/rel);files[k]=v
for rel in ['engine-speed/stage5/fair_player.py','engine-speed/stage5/derived_public_state.py','engine-speed/stage5b-r3/deadline_player.py','engine-speed/stage5b-r3/native/clasher_core.abi3.so','c56/engine/root-v3/human_deck_catalog.json','live-loop/l1/v3/evaluation-validation/selection.json','live-loop/l1/v3/evaluation-heldout/metrics.json']:
    p=ROOT/'reports/strategy_council_20260928'/rel;k,v=copy(p,Path('support')/p.name);files[k]=v
(HERE/'source-copies.json').write_text(json.dumps(files,indent=2)+'\n')
print('Copied',len(files),'files;',sum(p.stat().st_size for p in R.rglob('*') if p.is_file()),'bytes')
