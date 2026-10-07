"""Snapshot runtime locally. Run once on Mac for tests and once on hub before seal."""
from pathlib import Path
import hashlib
import json
import shutil
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
R=HERE/'runtime'
if (HERE/'evaluation-manifest.json').exists():raise RuntimeError('already frozen')
files={}
def copy(source,rel):
    dest=R/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    files[str(source.relative_to(ROOT))]={'copy':str(dest.relative_to(HERE)),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
for source in (ROOT/'src/clasher').rglob('*'):
    if source.is_file() and '__pycache__' not in source.parts and source.suffix in ('.py','.json','.csv'):copy(source,source.relative_to(ROOT))
for source in (ROOT/'engine-rs').glob('*.py'):copy(source,source.relative_to(ROOT))
for rel in ['gamedata.json','pyproject.toml','reports/strategy_council_20260928/engine-speed/es_common.py','reports/strategy_council_20260928/m0/data/roles_v2/training.json']:copy(ROOT/rel,Path(rel))
for rel in ['engine-speed/stage5/fair_player.py','engine-speed/stage5/derived_public_state.py','c56/engine/root-v3/human_deck_catalog.json']:
    source=ROOT/'reports/strategy_council_20260928'/rel;copy(source,Path('support')/source.name)
copy(HERE/'inputs/selection.json',Path('support/selection.json'))
copy(ROOT/'engine-rs/clasher_core.abi3.so',Path('support/clasher_core.abi3.so'))
files['engine_source_pins']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'engine-rs/src').rglob('*.rs')}
(HERE/'source-copies.json').write_text(json.dumps(files,indent=2)+'\n')
print('runtime snapshotted',len(files))
