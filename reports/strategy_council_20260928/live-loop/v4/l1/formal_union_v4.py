"""Authenticate full Phase A before opening a train/validation cache union.

Runtime connection files contain private paths, never selection/heldout authority.
Stable index snapshots retain full cache provenance across service restarts.
"""
import hashlib
import json
from pathlib import Path

from formal_guard import admit
from cache_union_v4 import UnionPixelCache
from pixel_cache import sha

EXTRA_SOURCES = ('union_training_v4.py','cache_union_v4.py','cache_transport_v4.py',
                 'cache_budget.py','formal_guard.py','reference_sample.py','formal_union_v4.py')


def open_formal_union(source, split, state, exit_receipt, saved_admission, runtime):
    admission=admit(state,exit_receipt,source,split,Path(__file__).parent)
    if json.loads(saved_admission.read_text())!=admission:
        raise ValueError('Formal cache admission differs from producer/population')
    rows=[]
    for name,expected in sorted(admission['receipts'].items()):
        path=Path(name)
        if path.parent.parent.resolve()!=source.resolve() or sha(path)!=expected:
            raise ValueError('Formal receipt path/hash differs')
        r=json.loads(path.read_text())
        if r['episode']!=path.parent.name:raise ValueError('Formal episode identity differs')
        if r['split'] in ('train','validation'):
            rows.append(dict(r,receipt_sha256=expected))
    if {r['split'] for r in rows}!={'train','validation'}:raise ValueError('Both formal populations required')
    expected={r['episode']:r['receipt_sha256'] for r in rows}
    config=json.loads(runtime.read_text())
    if (config.get('schema')!='clasher.v4.formal-union.v1'
            or config.get('admission_sha256')!=sha(saved_admission)
            or config.get('receipt_sha256')!=expected):
        raise ValueError('Formal union must cover exact authenticated train/validation population')
    return UnionPixelCache(rows,config['shards'])


def snapshot_indices(union, root):
    from cache_transport_v4 import RemotePixelCache
    pins={ep:digest for group in union.provenance for ep,digest in group['index_sha256'].items()}
    if set(pins)!=set(union.index):raise ValueError('Incomplete union index provenance')
    for ep in sorted(pins):
        reader=union.readers[ep]
        if isinstance(reader,RemotePixelCache):
            data=reader.request(dict(kind='index',episode=ep))
        else:data=(reader.root/ep/'index.json').read_bytes()
        if hashlib.sha256(data).hexdigest()!=pins[ep]:raise ValueError('Cache index changed before snapshot')
        target=root/ep/'index.json';target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if target.read_bytes()!=data:raise ValueError('Resume index snapshot differs')
        else:
            with target.open('xb') as f:f.write(data)
    return pins


def validate_provenance(manifest, populations, index_root):
    if manifest.get('formal_cache_union') is not True or manifest.get('engineering_only',False):
        raise ValueError('Formal union provenance required')
    pins={}
    for group in manifest['cache_union_provenance']:
        if set(pins)&set(group['index_sha256']):raise ValueError('Duplicate union provenance')
        pins.update(group['index_sha256'])
    expected=set(populations['train'])|set(populations['validation'])
    if set(pins)!=expected:raise ValueError('Union provenance omits formal population')
    if manifest['cache_index_sha256']!={ep:pins[ep] for ep in populations['train']}:
        raise ValueError('Training indices differ from full union')
    for ep,digest in pins.items():
        if sha(index_root/ep/'index.json')!=digest:raise ValueError('Saved union index changed')
    return pins
