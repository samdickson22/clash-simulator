"""Copy only S1 manifest-listed runtime bytes into the new S2 namespace."""
from pathlib import Path
import hashlib,json,shutil,socket
HERE=Path(__file__).resolve().parent
assert socket.gethostname().split('.')[0] in ('127x01','127x04','127x08')
source=HERE.parent/'search-noise-v2'
manifest=json.loads((source/'evaluation-manifest.json').read_text())
assert hashlib.sha256((source/'evaluation-manifest.json').read_bytes()).hexdigest()=='3ad63c0a7ad1634bac32bf5b031a7a312013497d8863aeaa3b0e2b0e077e5677'
copied={}
for rel,want in manifest['files'].items():
    if not rel.startswith(('runtime/','inputs/')):continue
    src=source/rel;dest=HERE/rel
    assert hashlib.sha256(src.read_bytes()).hexdigest()==want,rel
    if dest.exists():assert hashlib.sha256(dest.read_bytes()).hexdigest()==want,rel
    else:
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
    copied[rel]=want
(HERE/'runtime-provenance.json').write_text(json.dumps(dict(s1_manifest='3ad63c0a7ad1634bac32bf5b031a7a312013497d8863aeaa3b0e2b0e077e5677',files=copied),indent=2)+'\n')
print('verified runtime files',len(copied))
