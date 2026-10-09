"""Check every immutable training column, the mask table, static assets and init."""
import hashlib
import json
from pathlib import Path
import sys
root, inputs = map(Path, sys.argv[1:3])
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8<<20), b''): h.update(b)
    return h.hexdigest()
m = json.loads((root/'train/manifest.json').read_text())
for key, info in m['arrays'].items():
    assert sha(root/'train'/(key+'.npy')) == info['sha256'], key
parent = json.loads((root/'manifest.json').read_text())
assert parent['passed'] and parent['production'] and parent['version']=='v2'
assert sha(root/'train/manifest.json') == parent['role_manifests']['train']
assert sha(root/'mask_table.npy') == parent['mask_table_sha256']
asset = json.loads((inputs/'assets.npz.json').read_text())
assert sha(inputs/'assets.npz') == asset['asset_sha256']
receipt = dict(rows=m['rows'], train_manifest_sha256=sha(root/'train/manifest.json'),
    parent_manifest_sha256=sha(root/'manifest.json'),mask_sha256=sha(root/'mask_table.npy'),
    assets_sha256=sha(inputs/'assets.npz'),init_sha256=sha(inputs/'main02.pt'),
    checked_columns=len(m['arrays']),training_roles_only=True)
(inputs/'human-verified.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
