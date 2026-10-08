"""Detached train/validation cache producer; per-match atomic commits + SHA256."""
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import fcntl
import json
import math
from multiprocessing import Manager
import os
from pathlib import Path
import random
import shutil
import signal
import time
import uuid
import cv2
import numpy as np
from clasher.vision.l1_v4 import prepare_pixels
from pixel_cache import SCHEMA, PixelCache, encode, sha
from cache_budget import MAX_BYTES, MIN_FREE_BYTES, validate_root, used_bytes, reserved_bytes


def claim_bytes(ledger, lock, size):
    """Reserve aggregate payload space before writing; failed claims consume none.

    Successful claims are never refunded, even when a worker fails: partial
    files remain on disk. The parent's initial count includes older partials.
    """
    if size < 0:raise ValueError('Negative cache allocation')
    with lock:
        if size > ledger.value:
            raise RuntimeError('Aggregate cache space guard; incomplete files retained')
        ledger.value -= size


def one(args):
    root,cache,block_size,budget=args;root=Path(root);cache=Path(cache)
    r=json.loads((root/'receipt.json').read_text())
    if r['split'] not in ('train','validation'):raise ValueError('Heldout cache forbidden')
    r['receipt_sha256']=sha(root/'receipt.json');destination=cache/r['episode']
    if destination.exists():
        PixelCache(cache,[r]);return dict(episode=r['episode'],reused=True)
    for n in ('video.mp4','frames.jsonl'):
        if sha(root/n)!=r['files'][n]:raise ValueError('Source changed')
    # Unique incomplete attempts are retained on failure/reclaim, never overwritten.
    tmp=cache/(r['episode']+'.incomplete-'+uuid.uuid4().hex);tmp.mkdir(parents=True)
    cv2.setNumThreads(1)
    cap=cv2.VideoCapture(str(root/'video.mp4'),cv2.CAP_FFMPEG,[cv2.CAP_PROP_N_THREADS,1])
    raw=[];pixels=[];blocks=[];count=0;written=0;started=time.monotonic()
    with (tmp/'raw.zst').open('xb') as rf,(tmp/'pixels.zst').open('xb') as pf:
        while True:
            ok,img=cap.read()
            if not ok:break
            arena,hud=prepare_pixels(img);raw.append(img.ravel());pixels.append(np.concatenate((arena.ravel(),hud.ravel())))
            count+=1
            if len(raw)==block_size or count==r['frames']:
                block=dict(start=count-len(raw),count=len(raw))
                for name,file,frames in [('raw.zst',rf,raw),('pixels.zst',pf,pixels)]:
                    data=encode(frames)
                    if shutil.disk_usage(tmp).free-len(data)<MIN_FREE_BYTES+2*10**9:
                        raise RuntimeError('Cache space guard; incomplete files retained')
                    claim_bytes(*budget,len(data))
                    block[name]=[file.tell(),len(data)];file.write(data);written+=len(data)
                blocks.append(block);raw=[];pixels=[]
                if count% (block_size*16)==0:print(json.dumps(dict(episode=r['episode'],frames=count,bytes=written)),flush=True)
        rf.flush();pf.flush();os.fsync(rf.fileno());os.fsync(pf.fileno())
    cap.release()
    if count!=r['frames'] or raw:raise ValueError('Frame count differs from receipt')
    idx=dict(schema=SCHEMA,episode=r['episode'],split=r['split'],frames=count,block_size=block_size,blocks=blocks,
             video_sha256=r['files']['video.mp4'],receipt_sha256=r['receipt_sha256'],opencv=cv2.__version__,
             sha256={n:sha(tmp/n) for n in ('raw.zst','pixels.zst')},bytes=written,build_seconds=time.monotonic()-started,
             equality=dict(pass_=False))
    (tmp/'build-index.json').write_text(json.dumps(idx,indent=2)+'\n')
    # Independent sequential reference: CAP_PROP_POS_FRAMES is inaccurate for
    # the timestamped VFR source. Never accept a seek-based approximate frame.
    indices=sorted(random.Random(6111+r['seed']).sample(range(count),math.ceil(count*.01)))
    from pixel_cache import decompress, RAW, ARENA, HUD, PIXEL_BYTES
    checked=0
    selected=set(indices)
    cap=cv2.VideoCapture(str(root/'video.mp4'),cv2.CAP_FFMPEG,[cv2.CAP_PROP_N_THREADS,1])
    with (tmp/'raw.zst').open('rb') as rf,(tmp/'pixels.zst').open('rb') as pf:
        for i in range(count):
            ok,img=cap.read()
            if not ok:raise ValueError('Equality source truncated')
            if i not in selected:continue
            block=blocks[i//block_size];got=[]
            for name,file,width in [('raw.zst',rf,int(np.prod(RAW))),('pixels.zst',pf,PIXEL_BYTES)]:
                offset,size=block[name];file.seek(offset)
                got.append(decompress(file.read(size),(block['count'],width))[i%block_size])
            arena,hud=prepare_pixels(img)
            if not np.array_equal(got[0],img.ravel()) or not np.array_equal(got[1],np.concatenate((arena.ravel(),hud.ravel()))):
                raise ValueError(f'Exact equality failed: {r["episode"]} frame {i}')
            checked+=1
    cap.release()
    idx['equality']={'pass':True,'checked':checked,'frame_indices':indices,'seed':6111+r['seed'],'mismatches':0,
                     'reference':'independent sequential OpenCV decode + prepare_pixels, exact uint8'}
    (tmp/'index.json').write_text(json.dumps(idx,indent=2)+'\n')
    tmp.rename(destination)
    return dict(episode=r['episode'],frames=count,bytes=written,seconds=idx['build_seconds'],equality=idx['equality'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--split',type=Path,required=True);p.add_argument('--workers',type=int,default=4)
    p.add_argument('--block-size',type=int,default=16);p.add_argument('--limit',type=int,default=0)
    p.add_argument('--budget-gb',type=float,default=280);p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--inventory',type=Path,help='Optional explicit receipt-pinned train/validation subset')
    p.add_argument('--partition',type=int,default=0);p.add_argument('--partitions',type=int,default=1);a=p.parse_args()
    if not 1<=a.workers<=32:raise ValueError('Worker cap')
    if not 0<=a.partition<a.partitions or not 0<a.budget_gb*10**9<=MAX_BYTES:raise ValueError('Partition/budget invalid')
    validate_root(a.cache)
    if a.budget_gb*10**9 > reserved_bytes():raise ValueError('Build budget exceeds host reservation')
    lock=(a.cache/'.writer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if sha(a.split)!='3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258':raise ValueError('Split hash changed')
    members={r['seed']:r for r in json.loads(a.split.read_text())['matches']};rows=[]
    for q in sorted(a.source.glob('*/receipt.json')):
        r=json.loads(q.read_text())
        if r.get('split') not in ('train','validation') or not (q.parent/'video.mp4').exists():continue
        m=members[r['seed']]
        if (m['split'],m['decks'])!=(r['split'],r['decks']):raise ValueError('Membership changed')
        if (r['seed']-1975100700)%a.partitions!=a.partition:continue
        rows.append(q.parent)
    inventory_sha=None
    if a.inventory:
        inv=json.loads(a.inventory.read_text());pins=inv['receipt_sha256']
        if (inv.get('heldout_payloads_opened') is not False or len(inv['episodes'])!=len(set(inv['episodes']))
                or set(inv['episodes'])!=set(pins) or inv['matches']!=len(pins)):
            raise ValueError('Invalid explicit cache inventory')
        available={r.name:r for r in rows}
        if not set(pins)<=set(available) or any(sha(available[ep]/'receipt.json')!=digest for ep,digest in pins.items()):
            raise ValueError('Explicit inventory outside admitted source or receipt changed')
        rows=[available[ep] for ep in sorted(pins)];inventory_sha=sha(a.inventory)
    if a.limit:rows=rows[:a.limit]
    a.cache.mkdir(parents=True,exist_ok=True)
    used=used_bytes(a.cache)
    pending=[r for r in rows if not (a.cache/r.name/'index.json').exists()]
    # Compression varies substantially across matches. All workers claim from
    # one locked byte ledger, instead of prematurely exhausting a per-frame
    # allowance while other matches leave theirs unused. Reserve metadata/I/O.
    remaining=min(a.budget_gb*10**9-used,shutil.disk_usage(a.cache).free-MIN_FREE_BYTES)-2*10**9
    counts={r:json.loads((r/'receipt.json').read_text())['frames'] for r in pending}
    total_frames=sum(counts.values())
    if pending and (remaining<=0 or total_frames<=0):raise RuntimeError('Cache budget exhausted')
    stopping=False
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
        print('Stop requested; finish only current per-match commits',flush=True)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGUSR1,stop)
    results=[];todo=iter(rows)
    with Manager() as manager, ProcessPoolExecutor(a.workers) as pool:
        ledger=manager.Value('q',max(0,int(remaining)));allocation_lock=manager.Lock()
        active={}
        def submit():
            if stopping:return False
            r=next(todo,None)
            if r is None:return False
            active[pool.submit(one,(r,a.cache,a.block_size,(ledger,allocation_lock)))]=r
            return True
        for _ in range(a.workers):submit()
        while active:
            done,_=wait(active,return_when=FIRST_COMPLETED)
            for future in done:
                results.append(future.result());del active[future]
                submit()
    result=dict(matches=len(results),results=results,heldout_opened=False,cache=str(a.cache),
                partition=a.partition,partitions=a.partitions,bytes_on_host=used_bytes(a.cache),
                budget_bytes=int(a.budget_gb*10**9),minimum_free_bytes=MIN_FREE_BYTES,stopped=stopping,
                source_matches=len(rows),source_inventory_sha256=inventory_sha)
    with a.receipt.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(dict(matches=len(results),heldout_opened=False)),flush=True)
    if stopping:raise SystemExit(75)


if __name__=='__main__':main()
