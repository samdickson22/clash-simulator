"""Training-only crop study. Run on 127x03; outputs are ignored, never Git data."""
import argparse
import bisect
import ctypes
import ctypes.util
import gzip
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

SPLIT_SHA = '3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258'
ANCHORS = [(0, 9., 3.), (0, 3.5, 6.5), (0, 14.5, 6.5),
           (1, 9., 29.), (1, 3.5, 25.5), (1, 14.5, 25.5)]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def rows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt') as f:
        return [json.loads(x) for x in f]


def decode(blob, count):
    z = ctypes.CDLL(ctypes.util.find_library('zstd'))
    fn = z.ZSTD_decompress
    fn.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
    fn.restype = ctypes.c_size_t
    a = np.empty((count, 1140, 540, 3), np.uint8)
    if fn(a.ctypes.data, a.nbytes, blob, len(blob)) != a.nbytes:
        raise ValueError('Corrupt block')
    for i in range(1, count):
        np.bitwise_xor(a[i], a[i-1], out=a[i])
    return a


def run(a):
    cv2.setNumThreads(1)
    if sha(a.split) != SPLIT_SHA:
        raise ValueError('Frozen split changed')
    members = {r['seed']: r for r in json.loads(a.split.read_text())['matches']}
    # Membership is checked before opening any per-match payload or receipt.
    candidates = sorted(p.name for p in a.cache.iterdir()
                        if p.name.startswith('v4-phase-a-') and p.name.rsplit('-', 1)[-1].isdigit()
                        and members.get(int(p.name.rsplit('-', 1)[-1]), {}).get('split') == 'train')
    ranked = sorted(candidates, key=lambda e: hashlib.sha256(('tower-channel-v1:'+e).encode()).hexdigest())
    episodes = ranked[:32]
    manifest = dict(split_sha256=SPLIT_SHA, selection='SHA256(tower-channel-v1:episode), first 32 available training caches',
                    fit=episodes[:24], dev=episodes[24:], excluded_splits=['validation', 'heldout'],
                    validation_payloads_opened=False, heldout_payloads_opened=False)
    a.output.mkdir(parents=True, exist_ok=True)
    mp = a.output/'manifest.json'
    if mp.exists() and json.loads(mp.read_text()) != manifest:
        raise ValueError('Study manifest changed')
    mp.write_text(json.dumps(manifest, indent=2)+'\n')
    matrix = np.array(json.loads(a.geometry.read_text())['tile_to_pixel'])
    for ep in episodes:
        if a.part != 'all' and ep not in manifest[a.part]:
            continue
        out = a.output/ep
        if out.with_suffix('.npz').exists():
            continue
        folder = a.source/ep
        receipt = json.loads((folder/'receipt.json').read_text())
        member = members[receipt['seed']]
        if receipt['split'] != 'train' or member['split'] != 'train' or receipt['decks'] != member['decks']:
            raise ValueError('Training membership mismatch')
        idx = json.loads((a.cache/ep/'index.json').read_text())
        if idx['split'] != 'train' or idx['receipt_sha256'] != sha(folder/'receipt.json'):
            raise ValueError('Cache receipt mismatch')
        for name in ['frames.jsonl', 'objects.jsonl.gz', 'rich-objects.jsonl.gz']:
            if sha(folder/name) != receipt['files'][name]:
                raise ValueError('Truth pin mismatch')
        frames = rows(folder/'frames.jsonl')
        objects = rows(folder/'objects.jsonl.gz')
        rich = {r['tick']: {o['nativeObjectId']: o for o in r['objects']}
                for r in rows(folder/'rich-objects.jsonl.gz')}
        ticks = [r['tick'] for r in objects]
        labels = []
        for frame in frames:
            tick = (frame['tick_lo']+frame['tick_hi'])/2
            j = bisect.bisect_right(ticks, tick)-1
            known = [None]*6
            if j >= 0 and tick-ticks[j] <= 5:
                for o in objects[j]['objects']:
                    r = rich.get(ticks[j], {}).get(o['native_id'])
                    if r is None or any(o.get(k) != r.get(v) for k, v in
                                        [('owner','owner'),('card_id','cardId'),('x','x'),('y','y'),('hp','hp'),('max_hp','maxHp')]):
                        continue
                    if r.get('visibilityState') != 'visible' or (r.get('phaseRuntime') or {}).get('deployRemainingMs') != 0:
                        continue
                    for s, (side,x,y) in enumerate(ANCHORS):
                        if (o['owner'],o['x'],o['y'],o['card_id'],o['max_hp']) == (side,int(x*1000),int(y*1000),-1,4824 if s%3 == 0 else 3052):
                            known[s] = o['hp']
            labels.append(known)
        # All sparse coherent truth frames plus fixed ordinal samples for visual auditing.
        selected = [i for i, k in enumerate(labels) if any(v is not None for v in k) or i%64 == 0]
        sprites, hp_crops, meta = [], [], []
        for block in idx['blocks']:
            indices = [i for i in selected if block['start'] <= i < block['start']+block['count']]
            if not indices:
                continue
            offset, size = block['raw.zst']
            with (a.cache/ep/'raw.zst').open('rb') as f:
                f.seek(offset)
                blob = f.read(size)
            images = decode(blob, block['count'])
            for i in indices:
                image = images[i-block['start']]
                if i == selected[0] or i == selected[-1]:
                    cv2.imwrite(str(a.output/(ep+f'-{i}.jpg')), image)
                for s, (_, x, y) in enumerate(ANCHORS):
                    px, py = np.rint(matrix @ [x,y,1]).astype(int)
                    # Common-sized local sprite and HP panel crops.
                    sprites.append(image[py-95:py+55, px-48:px+48].copy())
                    offset = (-130 if s%3 == 0 else -110) if s < 3 else (20 if s%3 == 0 else -25)
                    hp_crops.append(image[py+offset:py+offset+80, px-55:px+55].copy())
                    meta.append(dict(episode=ep, ordinal=i, slot=s, hp=labels[i][s],
                                     timestamp_ms=frames[i].get('timestamp_ms'), tick=(frames[i]['tick_lo']+frames[i]['tick_hi'])/2))
        np.savez_compressed(out.with_suffix('.npz'), sprite=np.array(sprites), panel=np.array(hp_crops))
        out.with_suffix('.json').write_text(json.dumps(dict(rows=meta, receipt_sha256=sha(folder/'receipt.json'),
            cache_index_sha256=sha(a.cache/ep/'index.json'), cache_raw_sha256=idx['sha256']['raw.zst'],
            truth_sha256={n:receipt['files'][n] for n in ['frames.jsonl','objects.jsonl.gz','rich-objects.jsonl.gz']})))
        print(ep, len(selected), 'frames', sum(v is not None for k in labels for v in k), 'truth slots', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ['source', 'cache', 'split', 'geometry', 'output']:
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--part', choices=['fit','dev','all'], default='fit')
    run(p.parse_args())
