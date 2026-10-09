import hashlib
import json
from pathlib import Path
import sys
root=Path(sys.argv[1]);expected=sys.argv[2]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for part in iter(lambda:f.read(8<<20),b''):h.update(part)
    return h.hexdigest()
assert sha(root/'manifest.json')==expected,'corpus manifest SHA mismatch'
seal=json.loads((root/'manifest.json').read_text())
assert seal['complete'] and seal['packed'] and seal['rows']==38738534
total=0
for name,digest in seal['files'].items():
    p=(root/name).resolve();p.relative_to(root.resolve())
    assert sha(p)==digest,name
    total+=p.stat().st_size
receipt=dict(corpus_manifest_sha256=expected,rows=seal['rows'],
    checked_files=len(seal['files']),bytes=total,passed=True)
(root.parent/'corpus-copy.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
