"""Pin membership, derive native labels, and extract fit pixels on 127x03."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import cv2
import numpy as np
from extract import rows, sha, decode, SPLIT_SHA
from truth_r2 import derive
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'src'))
from clasher.live.tower_channel import MATRIX, ANCHORS


def episode_job(args):
    ep, source, cache, output, pixels = args
    cv2.setNumThreads(1)
    folder, cached = source/ep, cache/ep
    receipt = json.loads((folder/'receipt.json').read_text())
    idx = json.loads((cached/'index.json').read_text())
    if receipt['split'] != 'train' or idx['split'] != 'train' or idx['receipt_sha256'] != sha(folder/'receipt.json'):
        raise ValueError('Training provenance mismatch')
    for n in ('objects.jsonl.gz','rich-objects.jsonl.gz','frames.jsonl'):
        if sha(folder/n) != receipt['files'][n]:
            raise ValueError('Native truth hash mismatch')
    frames = rows(folder/'frames.jsonl')
    truth = derive(rows(folder/'objects.jsonl.gz'), rows(folder/'rich-objects.jsonl.gz'), frames, receipt['terminal'])
    truth['provenance'] = dict(receipt_sha256=sha(folder/'receipt.json'),cache_index_sha256=sha(cached/'index.json'),truth_sha256={n:receipt['files'][n] for n in ('objects.jsonl.gz','rich-objects.jsonl.gz','frames.jsonl')},raw_sha256=idx['sha256']['raw.zst'])
    (output/(ep+'.truth.json')).write_text(json.dumps(truth,separators=(',',':'))+'\n')
    if pixels:
        if sha(cached/'raw.zst') != idx['sha256']['raw.zst']:
            raise ValueError('Pixel checksum mismatch')
        selected = [i for i,l in enumerate(truth['labels']) if any(v is not None and v > 0 for v in l['hp']) or (i%32 == 0 and l['tick'] < receipt['terminal']['tick'])]
        sprites, panels, meta = [], [], []
        matrix = np.array(MATRIX)
        with (cached/'raw.zst').open('rb') as f:
            for b in idx['blocks']:
                indices = [i for i in selected if b['start'] <= i < b['start']+b['count']]
                if not indices:
                    continue
                offset,size = b['raw.zst'];f.seek(offset)
                images = decode(f.read(size),b['count'])
                for i in indices:
                    image=images[i-b['start']]
                    for s,(_,x,y) in enumerate(ANCHORS):
                        px,py=np.rint(matrix@[x,y,1]).astype(int)
                        sprites.append(image[py-95:py+55,px-48:px+48].copy())
                        offset=(-130 if s%3 == 0 else -110) if s<3 else (20 if s%3 == 0 else -25)
                        panels.append(image[py+offset:py+offset+80,px-55:px+55].copy())
                        l=truth['labels'][i]
                        meta.append(dict(ordinal=i,slot=s,state=l['states'][s],hp=l['hp'][s],active=l['active'][s],tick=l['tick']))
        np.savez_compressed(output/(ep+'.npz'),sprite=np.array(sprites),panel=np.array(panels))
        (output/(ep+'.json')).write_text(json.dumps(dict(rows=meta),separators=(',',':'))+'\n')
    print(ep,len(frames),'frames',len(truth['events']),'destructions',flush=True)
    return dict(episode=ep,events=truth['events'],terminal=receipt['terminal'],crown_score_fields=sorted(set(truth['crown_score_fields'])),provenance=truth['provenance'],schema_keys=truth['schema_keys'])


def main(a):
    if sha(a.split) != SPLIT_SHA:
        raise ValueError('Split pin mismatch')
    members={r['seed']:r for r in json.loads(a.split.read_text())['matches']}
    a.output.mkdir(parents=True,exist_ok=True)
    mp=a.output/'manifest.json'
    if a.mode == 'pin':
        old=json.loads(a.old.read_text())
        candidates=[p.name for p in a.cache.iterdir() if p.name.startswith('v4-phase-a-') and p.name.rsplit('-',1)[-1].isdigit() and members.get(int(p.name.rsplit('-',1)[-1]),{}).get('split') == 'train']
        ranked=sorted(candidates,key=lambda e:hashlib.sha256(('tower-channel-v1:'+e).encode()).hexdigest())
        fresh=[e for e in ranked if e not in old['fit']+old['dev']]
        manifest=dict(schema='clasher.public-tower-study.r2',split_sha256=SPLIT_SHA,selection='SHA256(tower-channel-v1:episode); first 8 remaining dev, next 24 remaining augment original 24 fit',fit=old['fit']+fresh[8:32],dev=fresh[:8],round1_excluded_from_dev=old['fit']+old['dev'],available_training_caches=len(ranked),validation_payloads_opened=False,heldout_payloads_opened=False)
        if mp.exists():
            raise ValueError('Manifest already pinned')
        mp.write_text(json.dumps(manifest,indent=2)+'\n');print(sha(mp));return
    manifest=json.loads(mp.read_text())
    assert not set(manifest['dev']) & (set(manifest['fit'])|set(manifest['round1_excluded_from_dev']))
    for ep in manifest['fit']+manifest['dev']:
        if members[int(ep.rsplit('-',1)[-1])]['split'] != 'train':
            raise ValueError('Forbidden membership')
    eps=manifest['fit'] if a.mode=='fit' else manifest['dev']
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        result=list(pool.map(episode_job,[(ep,a.source,a.cache,a.output,a.mode=='fit') for ep in eps]))
    (a.output/(a.mode+'-truth-receipt.json')).write_text(json.dumps(dict(manifest_sha256=sha(mp),episodes=result,pixels_opened=a.mode=='fit',workers=a.workers,host='127x03',nice=10),indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('split','old','source','cache','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--mode',choices=('pin','fit','dev-truth'),required=True)
    p.add_argument('--workers',type=int,default=8)
    main(p.parse_args())
