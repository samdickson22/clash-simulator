"""Read-only cache block transport over a caller-owned SSH loopback tunnel.

Server main must run under the fleet/lease wrapper. No arbitrary paths/ranges,
no heldout, no disk cache on clients. Training integration is separate.
"""
import argparse
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import numpy as np
from pixel_cache import PixelCache, SCHEMA, RAW, ARENA, HUD, PIXEL_BYTES, decompress, sha
from formal_guard import SPLIT_SHA


def stamp(path):
    s=path.stat()
    return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns


class RangeStore:
    def __init__(self, root, receipts, index_sha256):
        root=Path(root).resolve();receipts=list(receipts)
        episodes=[r['episode'] for r in receipts]
        if (len(episodes)!=len(set(episodes)) or set(episodes)!=set(index_sha256)
                or any('/' in e or not e.startswith('v4-phase-a-') for e in episodes)
                or any(r['split'] not in ('train','validation') for r in receipts)):
            raise ValueError('Exact safe cache episode set required')
        if any((root/e).resolve().parent!=root for e in episodes):
            raise ValueError('Cache path escapes approved root')
        self.root=root;self.indices={};self.stamps={}
        for ep in episodes:
            for name in ('index.json','raw.zst','pixels.zst'):
                if (root/ep/name).is_symlink():raise ValueError('Cache payload symlink refused')
            path=root/ep/'index.json';data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=index_sha256[ep]:
                raise ValueError('Pinned cache index changed')
            if set(json.loads(data)['sha256'])!={'raw.zst','pixels.zst'}:
                raise ValueError('Index names must be the two pixel payloads')
            self.indices[ep]=data
        self.cache=PixelCache(root,receipts)  # Full payload SHA and equality checks.
        for ep in episodes:
            for name in ('index.json','raw.zst','pixels.zst'):
                p=root/ep/name
                self.stamps[ep,name]=stamp(p)

    def read(self, request):
        ep=request.get('episode')
        if ep not in self.indices:raise ValueError('Episode outside admitted cache')
        kind=request.get('kind')
        if kind=='index':
            if stamp(self.root/ep/'index.json')!=self.stamps[ep,'index.json']:
                raise ValueError('Immutable index changed')
            return self.indices[ep]
        name,key=request.get('name'),request.get('block')
        if kind!='block' or name not in ('raw.zst','pixels.zst') or type(key) is not int:
            raise ValueError('Only indexed pixel blocks can be requested')
        blocks=self.cache.index[ep]['blocks']
        if not 0<=key<len(blocks):raise ValueError('Invalid block ordinal')
        offset,size=blocks[key][name];path=self.root/ep/name
        if not 0<size<=64*1024**2 or offset<0:raise ValueError('Invalid indexed block range')
        expected=self.stamps[ep,name]
        if stamp(path)!=expected:raise ValueError('Immutable payload changed')
        with path.open('rb') as f:
            f.seek(offset);data=f.read(size)
        if len(data)!=size or stamp(path)!=expected:raise ValueError('Truncated or changed payload')
        return data


def make_server(store, token, port=0):
    if not isinstance(token,str) or len(token)<32:raise ValueError('Private transport token required')
    slots=threading.BoundedSemaphore(8)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            if self.path!='/' or not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):
                self.send_error(403);return
            if not slots.acquire(blocking=False):self.send_error(503);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=8192:raise ValueError('Invalid request size')
                request=json.loads(self.rfile.read(length))
                if not isinstance(request,dict):raise ValueError('Object request required')
                data=store.read(request)
                self.send_response(200);self.send_header('Content-Type','application/octet-stream')
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except (ValueError,KeyError,TypeError,json.JSONDecodeError):self.send_error(400)
            finally:slots.release()
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    return server


class RemotePixelCache:
    def __init__(self, endpoint, token, receipts, index_sha256):
        url=urlsplit(endpoint)
        if url.scheme!='http' or url.hostname!='127.0.0.1' or url.path not in ('','/') or url.query or url.fragment or url.username:
            raise ValueError('Use an owned SSH tunnel on IPv4 loopback')
        self.endpoint=endpoint;self.token=token;self.index={}
        receipts=list(receipts)
        if len(receipts)!=len({r['episode'] for r in receipts}) or {r['episode'] for r in receipts}!=set(index_sha256):
            raise ValueError('Exact receipt/index population required')
        for r in receipts:
            if r['split'] not in ('train','validation'):raise ValueError('Heldout remote cache forbidden')
            ep=r['episode'];data=self.request(dict(kind='index',episode=ep))
            if hashlib.sha256(data).hexdigest()!=index_sha256[ep]:raise ValueError('Remote index hash mismatch')
            idx=json.loads(data)
            if (idx['schema']!=SCHEMA or idx['episode']!=ep or idx['split']!=r['split']
                    or idx['frames']!=r['frames'] or idx['receipt_sha256']!=r['receipt_sha256']
                    or idx['video_sha256']!=r['files']['video.mp4']
                    or idx['opencv']!=__import__('cv2').__version__
                    or idx['equality'].get('pass') is not True or idx['equality'].get('mismatches')!=0
                    or idx['equality']['checked']<math.ceil(.01*r['frames'])):
                raise ValueError('Remote cache identity/equality mismatch')
            self.index[ep]=idx

    def request(self, value):
        request=Request(self.endpoint,data=json.dumps(value).encode(),headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        with urlopen(request,timeout=60) as response:
            size=int(response.headers['Content-Length'])
            if not 0<size<=64*1024**2:raise ValueError('Remote response size invalid')
            data=response.read(size+1)
        if len(data)!=size:raise ValueError('Remote response truncated')
        return data

    def get(self, episode, indices, raw=False):
        idx=self.index[episode];name='raw.zst' if raw else 'pixels.zst'
        width=int(np.prod(RAW)) if raw else PIXEL_BYTES;blocks={};out=[]
        for i in indices:
            if type(i) is not int or not 0<=i<idx['frames']:raise IndexError(i)
            key=i//idx['block_size'];block=idx['blocks'][key]
            if key not in blocks:
                blob=self.request(dict(kind='block',episode=episode,name=name,block=key))
                if len(blob)!=block[name][1]:raise ValueError('Remote block size differs from pinned index')
                blocks[key]=decompress(blob,(block['count'],width))
            row=blocks[key][i%idx['block_size']]
            if raw:out.append(row.reshape(RAW).copy())
            else:out.append((row[:int(np.prod(ARENA))].reshape(ARENA).copy(),row[int(np.prod(ARENA)):].reshape(HUD).copy()))
        return out


def main():
    p=argparse.ArgumentParser()
    for name in ('source','cache','split','inventory','manifest','token-file','ready'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--port',type=int,default=0)
    p.add_argument('--max-seconds',type=int,default=600)
    p.add_argument('--probe-reference',type=Path)
    p.add_argument('--stop-file',type=Path)
    a=p.parse_args()
    if not 1<=a.max_seconds<=3600:raise ValueError('Bounded service lifetime required')
    if a.stop_file and a.stop_file.exists():raise ValueError('Use a fresh stop file')
    from cache_budget import validate_root
    validate_root(a.cache)
    if sha(a.split)!=SPLIT_SHA:raise ValueError('Frozen split changed')
    manifest=json.loads(a.manifest.read_text());inventory=json.loads(a.inventory.read_text())
    if (manifest.get('complete_for_snapshot') is not True or manifest.get('heldout_payloads_opened') is not False
            or manifest.get('source_snapshot_sha256')!=sha(a.inventory) or manifest.get('split_sha256')!=SPLIT_SHA
            or inventory.get('heldout_payloads_opened') is not False
            or set(inventory['receipt_sha256'])!=set(manifest['index_sha256'])):
        raise ValueError('Verified cache snapshot required')
    members={r['seed']:r for r in json.loads(a.split.read_text())['matches']};rows=[]
    for ep,digest in inventory['receipt_sha256'].items():
        if '/' in ep or not ep.startswith('v4-phase-a-'):raise ValueError('Invalid episode')
        path=a.source/ep/'receipt.json'
        if sha(path)!=digest:raise ValueError('Receipt changed')
        r=json.loads(path.read_text());m=members[r['seed']]
        if r['split'] not in ('train','validation') or (r['split'],r['decks'])!=(m['split'],m['decks']):raise ValueError('Receipt admission failed')
        rows.append(dict(r,receipt_sha256=digest))
    if a.token_file.stat().st_mode & 0o077:raise ValueError('Transport token must be private')
    token=a.token_file.read_text().strip()
    lock=(a.cache/'.writer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_SH|fcntl.LOCK_NB)
    store=RangeStore(a.cache,rows,manifest['index_sha256']);server=make_server(store,token,a.port)
    if a.probe_reference:
        import random
        checks=[]
        for r in rows:
            ep=r['episode']
            indices=sorted(random.Random(6112+r['seed']).sample(range(r['frames']),math.ceil(.01*r['frames'])))
            for raw in (False,True):
                samples=store.cache.get(ep,indices,raw=raw)
                hashes=[hashlib.sha256(x.tobytes() if raw else x[0].tobytes()+x[1].tobytes()).hexdigest() for x in samples]
                checks.append(dict(episode=ep,raw=raw,indices=indices,sha256=hashes))
        with a.probe_reference.open('x') as f:json.dump(dict(receipts=rows,checks=checks,
            manifest_sha256=sha(a.manifest),index_sha256=manifest['index_sha256'],heldout_payloads_opened=False),f)
    with a.ready.open('x') as f:json.dump(dict(port=server.server_port,manifest_sha256=sha(a.manifest),
        inventory_sha256=sha(a.inventory),index_sha256=manifest['index_sha256'],payloads_verified=True,
        heldout_payloads_opened=False,selection_seal=False),f,indent=2)
    deadline=time.monotonic()+a.max_seconds;server.timeout=1
    try:
        while time.monotonic()<deadline and not (a.stop_file and a.stop_file.exists()):
            server.handle_request()
    finally:server.server_close()


if __name__=='__main__':main()
