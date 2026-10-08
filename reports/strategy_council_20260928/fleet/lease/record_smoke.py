import hashlib,json,os
from pathlib import Path
b=Path(os.environ['CLASHER_LEASE_ROOT'])
s=(b/'jobs/p16.log').read_text()
print(s)
rows=[]
for line in s.splitlines():
    try: rows.append(json.loads(line))
    except ValueError: pass
assert rows, 'Missing checker JSON'
r=rows[-1]
print(r)
assert r['checked_episodes'] == 12 and r['mismatches'] == [], r
(b/'jobs/p16.json').write_text(json.dumps(r,indent=2)+'\n')
(b/'jobs/native.sha256').write_text(hashlib.sha256((b/'repo/engine-rs/clasher_core.abi3.so').read_bytes()).hexdigest()+'\n')
