"""Synthetic exact-population configuration checks, no service/heldout payloads."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from formal_cache_client_v4 import runtime_spec
from formal_guard import SPLIT_SHA
from pixel_cache import sha


def main(root):
    root.mkdir(exist_ok=False);source=root/'matches';shards=[];receipts={};checks=0
    def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x)+'\n')
    for i,split in enumerate(('train','validation','heldout')):
        ep=f'v4-phase-a-synthetic-{i}';rp=source/ep/'receipt.json'
        write(rp,dict(episode=ep,split=split,frames=10));receipts[str(rp)]=sha(rp)
        if split=='heldout':continue
        ip=root/f'inventory-{i}.json';mp=root/f'manifest-{i}.json'
        write(ip,dict(matches=1,episodes=[ep],receipt_sha256={ep:sha(rp)},heldout_payloads_opened=False))
        write(mp,dict(matches=1,frames=10,splits={s:int(s==split) for s in ('train','validation')},
            complete_for_snapshot=True,heldout_payloads_opened=False,split_sha256=SPLIT_SHA,
            source_snapshot_sha256=sha(ip),files_verified=2,equality_checked=1,equality_mismatches=0,index_sha256={ep:'1'*64}))
        shards.append(dict(kind='remote',inventory=str(ip),manifest=str(mp)))
    proof=dict(receipts=receipts);result=runtime_spec(proof,'a'*64,source,shards)
    assert len(result['receipt_sha256'])==2 and result['schema']=='clasher.v4.formal-union.v1';checks+=1
    def refuses(fn):
        nonlocal checks
        try:fn()
        except ValueError:checks+=1
        else:raise AssertionError('Invalid formal client configuration admitted')
    refuses(lambda:runtime_spec(proof,'a'*64,source,shards[:1]))
    refuses(lambda:runtime_spec(proof,'a'*64,source,shards+shards[:1]))
    bad=deepcopy(proof);bad['receipts'][next(iter(receipts))]='0'*64
    refuses(lambda:runtime_spec(bad,'a'*64,source,shards))
    outside=root/'outside/receipt.json';write(outside,dict(episode='outside',split='train',frames=1))
    bad=deepcopy(proof);bad['receipts'][str(outside)]=sha(outside)
    refuses(lambda:runtime_spec(bad,'a'*64,source,shards))
    print(json.dumps(dict(checks=checks,pass_=True,synthetic_only=True,heldout_payloads_opened=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
