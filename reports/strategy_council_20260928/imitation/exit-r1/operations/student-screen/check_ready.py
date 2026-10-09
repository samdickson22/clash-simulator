"""Pre-fit checkpoint identity, static assets and verified training inputs."""
import json
from pathlib import Path
import sys
import torch
from imitation.exit_r1.student import initialize
from imitation.model.store import PackedStore
from imitation.exit_r1.rows import sha
p=Path(sys.argv[1])
receipt=json.loads((p/'inputs/human-verified.json').read_text())
assert receipt['init_sha256']=='d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed'
ck=torch.load(p/'inputs/main02.pt',map_location='cpu',weights_only=True)
assert ck['state']['step']==22552 and ck['config']['width']==192
model,c=initialize(p/'inputs/main02.pt')
store=PackedStore(p/'human/train','train',p/'inputs/assets.npz')
for k,b in (('costs','costs'),('descriptors','descriptors'),('tiles','tile_features')):
    assert torch.equal(getattr(model,b).cpu(),torch.from_numpy(store.assets[k])),k
parent=json.loads((p/'human/manifest.json').read_text())
assert receipt['mask_sha256']==parent['mask_table_sha256']
assert receipt['train_manifest_sha256']==parent['role_manifests']['train']
assert receipt['assets_sha256']==sha(p/'inputs/assets.npz')
receipt.update(dev_manifest_sha256=parent['role_manifests']['dev'],
    init_step=22552,width=192,static_buffers_equal=True)
(p/'inputs/pre-fit-verified.json').write_text(json.dumps(receipt,indent=2)+'\n')
(p/'fit-ready.txt').write_text('v1 step22552 width192 assets and input SHA PASS\n')
print(json.dumps(receipt))
