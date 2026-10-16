"""Generate synthetic frames in shards (resumable; one pool worker per shard).

  python gen_shards.py --bank BANK --out OUT --tag 03a --shards 0:10 [--per-shard 1000] [--workers 32] [--seed 1]
                       [--cfg '{"p_official": .6}'] [--weights weights.json] [--quality 90]

OUT/<tag>-<k:05d>/ = images/<id>.jpg, labels/<id>.txt (KataCR: name_idx cx cy w h belong, normalised to 568x896),
meta.jsonl (per frame: bg, arena, units [name, belong, box px, src, swap, sprite, tile]), DONE.json (counts per name/team).
A shard is written to a hidden tmp dir and renamed when complete, so a killed run leaves no partial shard; reruns skip
shards that have DONE.json. Frame ids are <tag>-<k:05d>-<i:04d>; per-frame RNG seed = f(seed, tag, k, i), reproducible.
Run with exactly --workers python processes (one per pool worker), so `cpu_job.sh N` leases match.
"""
import argparse
import json
import os
import shutil
import sys
import time
import zlib
from collections import Counter
from multiprocessing import get_context
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('NUMPY_MADVISE_HUGEPAGE', '0')
import cv2  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compose import Bank, Composer, yolo_lines, frame_seed  # noqa: E402

cv2.setNumThreads(1)
G = {}


def run_shard(k):
    a = G['args']
    name = f'{a.tag}-{k:05d}'
    final = Path(a.out)/name
    if (final/'DONE.json').exists():
        return name, None
    tmp = Path(a.out)/f'.{name}.tmp'
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp/'images').mkdir(parents=True); (tmp/'labels').mkdir()
    comp = G['comp']
    tag_hash = zlib.crc32(a.tag.encode())
    counts, n_boxes, t0 = Counter(), 0, time.time()
    with open(tmp/'meta.jsonl', 'w') as mf:
        for i in range(a.per_shard):
            fid = f'{name}-{i:04d}'
            rng = np.random.default_rng([a.seed, tag_hash, k, i])
            img, labels, meta = comp.frame(rng)
            cv2.imwrite(str(tmp/'images'/f'{fid}.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, a.quality])
            (tmp/'labels'/f'{fid}.txt').write_text(yolo_lines(labels))
            meta['id'] = fid
            mf.write(json.dumps(meta)+'\n')
            for idx, b, *_ in labels:
                counts[f'{idx}_{b}'] += 1
            n_boxes += len(labels)
    done = dict(shard=name, frames=a.per_shard, boxes=n_boxes, seconds=round(time.time()-t0, 1), seed=a.seed,
                cfg=G['cfg'], weights=G['weights'], counts=dict(counts), created=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    (tmp/'DONE.json').write_text(json.dumps(done))
    if final.exists():
        shutil.rmtree(final)
    os.rename(tmp, final)
    return name, done


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bank', required=True)
    p.add_argument('--classes', default=str(Path(__file__).resolve().parent/'classes.json'))
    p.add_argument('--out', required=True)
    p.add_argument('--tag', required=True)
    p.add_argument('--shards', required=True, help='a:b (shard indices a..b-1)')
    p.add_argument('--per-shard', type=int, default=1000)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--quality', type=int, default=90)
    p.add_argument('--cfg', default='{}')
    p.add_argument('--weights', default=None, help='json {name: weight} for unit class sampling')
    a = p.parse_args()
    lo, hi = map(int, a.shards.split(':'))
    Path(a.out).mkdir(parents=True, exist_ok=True)
    cfg = json.loads(a.cfg)
    weights = json.loads(Path(a.weights).read_text()) if a.weights else None
    t0 = time.time()
    bank = Bank(a.bank, a.classes)
    G.update(args=a, cfg=cfg, weights=a.weights or 'default_weights', comp=Composer(bank, cfg, weights))
    print(f'bank: {len(bank.bgs)} floors ({len(bank.off_bgs)} official), {len(bank.unit_names)} unit names, '
          f'{sum(len(v) for d in bank.sprites.values() for v in d.values())} cut-outs, load {time.time()-t0:.1f}s', flush=True)
    todo = [k for k in range(lo, hi) if not (Path(a.out)/f'{a.tag}-{k:05d}'/'DONE.json').exists()]
    print(f'{len(todo)} shards to do of {hi-lo}', flush=True)
    with get_context('fork').Pool(a.workers, maxtasksperchild=50) as pool:
        for name, done in pool.imap_unordered(run_shard, todo):
            if done:
                print(f"{time.strftime('%H:%M:%S')} {name} {done['frames']} frames {done['boxes']} boxes {done['seconds']}s", flush=True)
    print('ALL DONE', flush=True)


if __name__ == '__main__':
    main()
