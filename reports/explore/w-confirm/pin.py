"""Record immutable runtime identities without touching other owners' files."""
import hashlib
import json
import os
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[3]
job=root.parent
files=[p for folder in ('src','engine-rs','reports/explore/w-confirm',
       'reports/strategy_council_20260928/engine-speed/stage5',
       'reports/strategy_council_20260928/search-noise-s6')
       for p in (root/folder).rglob('*.py')]
files += [root/p for p in ('gamedata.json','hitboxes.json',
    'reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json',
    'reports/strategy_council_20260928/m0/data/roles_v2/training.json')]
hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
receipt=dict(python=sys.version,config_sha256=hashlib.sha256((root/'reports/explore/w-confirm/config.json').read_bytes()).hexdigest(),
    native_sha256=hashlib.sha256((job/'native/clasher_core.abi3.so').read_bytes()).hexdigest(),
    reference_native_sha256=hashlib.sha256((job/'reference/clasher_core.abi3.so').read_bytes()).hexdigest(),
    source_manifest_sha256=hashlib.sha256((job/'native-source/w-source-manifest.json').read_bytes()).hexdigest(),
    files=hashes,manifest_sha256=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
    freeze_commit='e006fdba',nice=os.getpriority(os.PRIO_PROCESS,0),scheduler=os.sched_getscheduler(0),
    cache_root=str(job/'cache'))
(job/'runtime-pin.json').write_text(json.dumps(receipt,indent=2)+'\n')
