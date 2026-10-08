"""Read-only verification of this run and the sealed S1/S2 inputs."""
from pathlib import Path
import hashlib,json,socket,time
HERE=Path(__file__).resolve().parent
out=dict(host=socket.gethostname(),utc=time.time(),studies={})
for name in ('search-noise-v2','search-noise-s2','search-noise-s3','search-noise-s4'):
 folder=HERE.parent/name;manifest=folder/'evaluation-manifest.json'
 if not manifest.exists():continue
 data=json.loads(manifest.read_text());bad=[]
 for rel,want in data['files'].items():
  path=folder/rel
  if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=want:bad.append(rel)
 out['studies'][name]=dict(files=len(data['files']),mismatches=bad,manifest=hashlib.sha256(manifest.read_bytes()).hexdigest())
(HERE/f'final-integrity-{socket.gethostname().split(".")[0]}.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out));assert all(not d['mismatches'] for d in out['studies'].values())
