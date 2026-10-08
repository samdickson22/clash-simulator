"""Synthetic union rejection and real local/loopback routing checks on a lease."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import threading
import cv2
import numpy as np
from cache_union_v4 import partition,UnionPixelCache
from cache_transport_v4 import RangeStore,make_server
from formal_guard import SPLIT_SHA
from pixel_cache import RAW,PIXEL_BYTES,SCHEMA,encode,sha


def main(root,out):
    out.mkdir(exist_ok=False);rows=[];evidence=[];specs=[];checks=0
    def check(value):
        nonlocal checks
        assert value;checks+=1
    def refuses(fn):
        nonlocal checks
        try:fn()
        except (ValueError,KeyError,BlockingIOError):checks+=1
        else:raise AssertionError('Invalid union accepted')
    for i,split in enumerate(('train','validation')):
        ep=f'v4-phase-a-union-synthetic-{out.name}-{i}';folder=root/ep;folder.mkdir()
        r=dict(episode=ep,split=split,frames=2,receipt_sha256=str(i+1)*64,files={'video.mp4':'b'*64});rows.append(r)
        block=dict(start=0,count=2)
        for name,width in [('raw.zst',int(np.prod(RAW))),('pixels.zst',PIXEL_BYTES)]:
            data=encode([np.full(width,v+i,np.uint8) for v in (3,7)])
            (folder/name).write_bytes(data);block[name]=[0,len(data)]
        idx=dict(schema=SCHEMA,episode=ep,split=split,frames=2,receipt_sha256=r['receipt_sha256'],video_sha256='b'*64,
            opencv=cv2.__version__,block_size=2,blocks=[block],sha256={n:sha(folder/n) for n in ('raw.zst','pixels.zst')},
            equality={'pass':True,'checked':1,'mismatches':0})
        (folder/'index.json').write_text(json.dumps(idx))
        inv=dict(matches=1,episodes=[ep],receipt_sha256={ep:r['receipt_sha256']},heldout_payloads_opened=False)
        ip=out/f'inventory-{i}.json';ip.write_text(json.dumps(inv))
        m=dict(matches=1,frames=2,splits={s:int(s==split) for s in ('train','validation')},complete_for_snapshot=True,
            source_snapshot_sha256=sha(ip),split_sha256=SPLIT_SHA,index_sha256={ep:sha(folder/'index.json')},
            files_verified=2,equality_checked=1,equality_mismatches=0,heldout_payloads_opened=False)
        mp=out/f'manifest-{i}.json';mp.write_text(json.dumps(m))
        evidence.append(dict(inventory=inv,manifest=m,inventory_sha256=sha(ip)))
        specs.append(dict(kind='local',cache=root,inventory=ip,manifest=mp))
    check(partition(rows,evidence)==[[rows[0]],[rows[1]]])
    refuses(lambda:partition([],evidence));refuses(lambda:partition(rows+rows[:1],evidence))
    refuses(lambda:partition(rows,[]));refuses(lambda:partition(rows,evidence[:1]))
    refuses(lambda:partition(rows,evidence+evidence[:1]));refuses(lambda:partition(rows[:1],evidence))
    for key,value in [('split','heldout'),('frames',0),('frames',True),('episode','../escape'),('receipt_sha256','f'*64)]:
        bad=deepcopy(rows);bad[0][key]=value;refuses(lambda:partition(bad,evidence))
    for key,value in [('matches',2),('episodes',[]),('episodes',[rows[0]['episode']]*2),
                      ('heldout_payloads_opened',True),('receipt_sha256',{})]:
        bad=deepcopy(evidence);bad[0]['inventory'][key]=value;refuses(lambda:partition(rows,bad))
    for key,value in [('complete_for_snapshot',False),('heldout_payloads_opened',True),('split_sha256','f'*64),
                      ('source_snapshot_sha256','f'*64),('index_sha256',{}),('matches',2),('files_verified',1),
                      ('equality_mismatches',1),('equality_checked',0),('frames',3),('splits',{'train':0,'validation':1}),
                      ('index_sha256',{rows[0]['episode']:'not-a-hash'})]:
        bad=deepcopy(evidence);bad[0]['manifest'][key]=value;refuses(lambda:partition(rows,bad))
    # Real local shard + authenticated loopback shard, neither can fill in the other.
    pins=evidence[1]['manifest']['index_sha256'];store=RangeStore(root,rows[1:],pins)
    token='union-synthetic-test-'+'x'*32;tp=out/'token';tp.touch(mode=0o600);tp.write_text(token)
    server=make_server(store,token);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    ready=dict(payloads_verified=True,heldout_payloads_opened=False,index_sha256=pins,
        manifest_sha256=sha(specs[1]['manifest']),inventory_sha256=sha(specs[1]['inventory']))
    rp=out/'ready.json';rp.write_text(json.dumps(ready))
    specs[1]=dict(specs[1],kind='remote',ready=rp,token_file=tp,endpoint=f'http://127.0.0.1:{server.server_port}/')
    try:
        with UnionPixelCache(rows,specs) as union:
            check(set(union.index)=={r['episode'] for r in rows})
            for i,r in enumerate(rows):
                check(all(np.all(x==v+i) for x,v in zip(union.get(r['episode'],[1,0],raw=True),(7,3))))
                check(all(np.all(a==v+i) and np.all(h==v+i) for (a,h),v in zip(union.get(r['episode'],[0,1]),(3,7))))
            check('token' not in json.dumps(union.provenance) and len(union.provenance)==2)
            refuses(lambda:union.get('unlisted',[0]))
        bad=deepcopy(ready);bad['manifest_sha256']='f'*64;rp.write_text(json.dumps(bad))
        refuses(lambda:UnionPixelCache(rows,specs));rp.write_text(json.dumps(ready))
        tp.chmod(0o644);refuses(lambda:UnionPixelCache(rows,specs));tp.chmod(0o600)
        # Wrong/incomplete metadata must fail before opening any local payload.
        broken=[dict(specs[0],cache=out/'does-not-exist')]
        refuses(lambda:UnionPixelCache(rows,broken))
    finally:server.shutdown();server.server_close();thread.join()
    result=dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)
    (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();main(a.cache,a.output)
