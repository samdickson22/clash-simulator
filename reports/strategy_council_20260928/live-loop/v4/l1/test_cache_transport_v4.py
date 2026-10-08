"""Synthetic loopback exactness/refusal tests; run only under fleet wrapper."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import threading
from urllib.error import HTTPError
import cv2
import numpy as np
from cache_transport_v4 import RangeStore,RemotePixelCache,make_server
from pixel_cache import RAW,ARENA,HUD,PIXEL_BYTES,SCHEMA,encode,sha


def main(root):
    checks=0
    def check(v):
        nonlocal checks
        assert v;checks+=1
    def refuses(fn):
        nonlocal checks
        try:fn()
        except (ValueError,IndexError,HTTPError):checks+=1
        else:raise AssertionError('Invalid request accepted')
    root.mkdir();ep='v4-phase-a-synthetic';folder=root/ep;folder.mkdir()
    receipt=dict(episode=ep,split='train',frames=2,receipt_sha256='a'*64,files={'video.mp4':'b'*64})
    raw=[np.full(int(np.prod(RAW)),v,np.uint8) for v in (3,7)]
    pixels=[np.full(PIXEL_BYTES,v,np.uint8) for v in (5,9)]
    block=dict(start=0,count=2)
    for name,frames in [('raw.zst',raw),('pixels.zst',pixels)]:
        data=encode(frames);(folder/name).write_bytes(data);block[name]=[0,len(data)]
    idx=dict(schema=SCHEMA,episode=ep,split='train',frames=2,receipt_sha256='a'*64,video_sha256='b'*64,
        opencv=cv2.__version__,block_size=2,blocks=[block],sha256={n:sha(folder/n) for n in ('raw.zst','pixels.zst')},
        equality={'pass':True,'checked':1,'mismatches':0})
    (folder/'index.json').write_text(json.dumps(idx));pins={ep:sha(folder/'index.json')}
    store=RangeStore(root,[receipt],pins);token='synthetic-token-'+'x'*32
    server=make_server(store,token);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}/'
    try:
        client=RemotePixelCache(url,token,[receipt],pins)
        got=client.get(ep,[1,0,1],raw=True)
        check(all(np.array_equal(a.ravel(),raw[i]) for a,i in zip(got,[1,0,1])))
        got=client.get(ep,[0,1])
        check(all(np.array_equal(np.concatenate((a.ravel(),h.ravel())),pixels[i]) for i,(a,h) in enumerate(got)))
        refuses(lambda:RemotePixelCache(url,'incorrect-token',[receipt],pins))
        refuses(lambda:RemotePixelCache(url,token,[dict(receipt,split='heldout')],pins))
        refuses(lambda:RemotePixelCache(url,token,[receipt],{ep:'c'*64}))
        refuses(lambda:RemotePixelCache('http://127x16:1234',token,[receipt],pins))
        refuses(lambda:client.get(ep,[-1]))
        refuses(lambda:client.get(ep,[2]))
        refuses(lambda:client.request(dict(kind='block',episode='../outside',name='raw.zst',block=0)))
        refuses(lambda:client.request(dict(kind='block',episode=ep,name='receipt.json',block=0)))
        refuses(lambda:client.request(dict(kind='block',episode=ep,name='raw.zst',block=True)))
        refuses(lambda:client.request(dict(kind='block',episode=ep,name='raw.zst',block=10)))
        # Immutable evidence mutation is refused, including same-length bytes.
        (folder/'raw.zst').write_bytes((folder/'raw.zst').read_bytes())
        refuses(lambda:client.get(ep,[0],raw=True))
        (folder/'index.json').write_text(json.dumps(idx)+' ')
        refuses(lambda:client.request(dict(kind='index',episode=ep)))
    finally:server.shutdown();server.server_close();thread.join()
    # Validate index file allowlist before reading any named payload.
    bad=deepcopy(idx);bad['sha256']['../../outside']='d'*64
    (folder/'index.json').write_text(json.dumps(bad))
    refuses(lambda:RangeStore(root,[receipt],{ep:sha(folder/'index.json')}))
    refuses(lambda:RangeStore(root,[dict(receipt,split='heldout')],pins))
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
