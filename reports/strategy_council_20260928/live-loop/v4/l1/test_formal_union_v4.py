"""Synthetic full-population/producer boundaries and immutable index snapshots."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import formal_union_v4 as gate
from cache_transport_v4 import RemotePixelCache


def main(root):
    root.mkdir();source=root/'source';source.mkdir();checks=0
    def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v)+'\n')
    def check(v):
        nonlocal checks
        assert v;checks+=1
    def refuses(fn):
        nonlocal checks
        try:fn()
        except ValueError:checks+=1
        else:raise AssertionError('Invalid formal union accepted')
    state=root/'state';ex=root/'exit';saved=root/'admission';runtime=root/'runtime'
    put(state,dict(stage='phase-a'));put(ex,dict(code=0))
    def invoke():return gate.open_formal_union(source,root/'split',state,ex,saved,runtime)
    with patch.object(gate,'UnionPixelCache',side_effect=AssertionError('Premature pixels')):
        refuses(invoke)
    proof=dict(receipts={});populations={'train':{},'validation':{}}
    for ep,split in [('v4-phase-a-1','train'),('v4-phase-a-2','validation'),('v4-phase-a-3','heldout')]:
        p=source/ep/'receipt.json';put(p,dict(episode=ep,split=split))
        proof['receipts'][str(p)]=gate.sha(p)
        if split in populations:populations[split][ep]=gate.sha(p)
    put(saved,proof);allpins={**populations['train'],**populations['validation']}
    config=dict(schema='clasher.v4.formal-union.v1',admission_sha256=gate.sha(saved),receipt_sha256=allpins,shards=[])
    put(runtime,config);captured=[]
    def cache(rows,shards):captured.extend(rows);return 'reader'
    with patch.object(gate,'admit',return_value=proof),patch.object(gate,'UnionPixelCache',side_effect=cache):
        check(invoke()=='reader');check({r['split'] for r in captured}=={'train','validation'})
        for change in ({'schema':'clasher.v4.engineering-union.v1'}, {'admission_sha256':'0'*64},
                       {'receipt_sha256':populations['train']}, {'receipt_sha256':{**allpins,'v4-phase-a-3':'a'*64}}):
            bad=deepcopy(config);bad.update(change);put(runtime,bad);refuses(invoke)
        put(runtime,config);put(saved,{});refuses(invoke);put(saved,proof)
        p=source/'v4-phase-a-1/receipt.json';original=p.read_bytes();put(p,{});refuses(invoke);p.write_bytes(original)
    local=root/'local';put(local/'v4-phase-a-1/index.json',dict(synthetic=1))
    remote_bytes=b'{"synthetic":2}\n'
    remote=object.__new__(RemotePixelCache);remote.request=lambda request:remote_bytes
    import hashlib
    pins={'v4-phase-a-1':gate.sha(local/'v4-phase-a-1/index.json'),
          'v4-phase-a-2':hashlib.sha256(remote_bytes).hexdigest()}
    union=SimpleNamespace(index={ep:{} for ep in pins},readers={'v4-phase-a-1':SimpleNamespace(root=local),'v4-phase-a-2':remote},
        provenance=[dict(index_sha256=pins,manifest_sha256='a'*64,inventory_sha256='b'*64)])
    snapshot=root/'indices'
    check(gate.snapshot_indices(union,snapshot)==pins)
    check((snapshot/'v4-phase-a-2/index.json').read_bytes()==remote_bytes)
    check(gate.snapshot_indices(union,snapshot)==pins)
    manifest=dict(formal_cache_union=True,engineering_only=False,cache_union_provenance=union.provenance,
                  cache_index_sha256={'v4-phase-a-1':pins['v4-phase-a-1']})
    check(gate.validate_provenance(manifest,populations,snapshot)==pins)
    for change in ({'formal_cache_union':False},{'engineering_only':True},
                   {'cache_union_provenance':[]},{'cache_union_provenance':union.provenance*2},
                   {'cache_index_sha256':{}}):
        bad=deepcopy(manifest);bad.update(change)
        refuses(lambda:gate.validate_provenance(bad,populations,snapshot))
    p=snapshot/'v4-phase-a-1/index.json';p.write_text('{}')
    refuses(lambda:gate.validate_provenance(manifest,populations,snapshot))
    refuses(lambda:gate.snapshot_indices(union,snapshot))
    remote.request=lambda request:b'changed'
    refuses(lambda:gate.snapshot_indices(union,root/'changed-remote'))
    check(not (source/'v4-phase-a-3/video.mp4').exists())
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
