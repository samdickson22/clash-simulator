"""Strict read-only checks of sealed studies and final S4 tracker inputs."""
from pathlib import Path
import hashlib,json,socket,time
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
out=dict(host=socket.gethostname(),utc=time.time(),studies={})
for name in ('search-noise-v2','search-noise-s2','search-noise-s3','search-noise-s4','search-noise-s5','search-noise-s6'):
 folder=HERE.parent/name;manifest=folder/'evaluation-manifest.json'
 if name=='search-noise-s6' and not manifest.exists():continue
 data=json.loads(manifest.read_text());bad=[]
 for rel,want in data['files'].items():
  path=folder/rel
  if not path.exists() or sha(path)!=want:bad.append(rel)
 out['studies'][name]=dict(files=len(data['files']),mismatches=bad,manifest=sha(manifest))
inputs=json.loads((HERE/'frozen-s4-inputs.json').read_text())
out['s4_tracker_mismatches']=[n for n,h in inputs.items() if sha(HERE/n)!=h or sha(HERE.parent/'search-noise-s4'/n)!=h]
path=HERE/f'integrity-{socket.gethostname().split(".")[0]}-{time.time_ns()}.json'
path.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
assert not out['s4_tracker_mismatches'] and all(not d['mismatches'] for d in out['studies'].values())
