"""Build the missing train/val pixel caches (pixels.zst only, same schema/index) into the job dir.

01 holds only part of the formal cache union; the rest lived on other hosts. Same
prepare_pixels + XOR/zstd block encoding as l1/build_cache.py, minus raw frames.
"""
import argparse
import json
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import common as C


def one(args):
    ep, split, out = args
    import cv2
    from clasher.vision.l1_v4 import prepare_pixels
    from pixel_cache import SCHEMA, encode
    guard = C.HeldoutGuard(); guard.check([ep])
    dest = Path(out)/ep
    if (dest/'index.json').exists():
        return ep, 'cached'
    r = C.load_receipt(guard, ep, split)
    tmp = Path(out)/(ep+'.incomplete'); tmp.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(1); t0 = time.time()
    cap = cv2.VideoCapture(str(C.MATCHES/ep/'video.mp4'), cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 1])
    blocks, buf, count = [], [], 0
    with (tmp/'pixels.zst').open('wb') as pf:
        while True:
            ok, img = cap.read()
            if not ok:
                break
            a, h = prepare_pixels(img); buf.append(np.concatenate((a.ravel(), h.ravel()))); count += 1
            if len(buf) == 16:
                data = encode(buf); blocks.append({'start': count-len(buf), 'count': len(buf), 'pixels.zst': [pf.tell(), len(data)]})
                pf.write(data); buf = []
        if buf:
            data = encode(buf); blocks.append({'start': count-len(buf), 'count': len(buf), 'pixels.zst': [pf.tell(), len(data)]})
            pf.write(data)
    cap.release()
    if count != r['frames']:
        raise ValueError(f'{ep}: decoded {count} != receipt {r["frames"]}')
    idx = dict(schema=SCHEMA, episode=ep, split=split, frames=count, block_size=16, blocks=blocks,
               video_sha256=r['files']['video.mp4'], opencv=cv2.__version__, build_seconds=time.time()-t0,
               note='live-perception exploration cache: pixels only, no raw, no equality audit')
    (tmp/'index.json').write_text(json.dumps(idx)+'\n'); tmp.rename(dest)
    return ep, f'built {time.time()-t0:.0f}s'


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, default=C.LOCAL_CACHE)
    p.add_argument('--workers', type=int, default=10); a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    guard = C.HeldoutGuard()
    jobs = [(ep, s, str(a.out)) for s in ('validation', 'train') for ep in guard.episodes(s)
            if not (C.CACHE/ep/'index.json').exists()]
    guard.check([j[0] for j in jobs]); print('missing', len(jobs), flush=True)
    with Pool(a.workers) as pool:
        for k, (ep, st) in enumerate(pool.imap_unordered(one, jobs)):
            print(k+1, len(jobs), ep, st, flush=True)
    print('done', flush=True)
