"""Audit only registered fit captures for crown/result availability, on 03."""
import json
from pathlib import Path
import cv2
import numpy as np
from extract import decode, rows, sha, SPLIT_SHA

ROOT = Path(__file__).resolve().parents[5]
STUDY = Path(__file__).resolve().parent
OUT = STUDY/'runtime/r3'
SOURCE = ROOT.parent/'clasher-v4-cpu/matches'
CACHE = ROOT.parent/'clasher-v4-cache'

def main():
    cv2.setNumThreads(1)
    OUT.mkdir(parents=True, exist_ok=True)
    split = STUDY.parent/'split.json'
    assert sha(split) == SPLIT_SHA
    members = {r['seed']:r['split'] for r in json.loads(split.read_text())['matches']}
    manifest = json.loads((STUDY/'round2-manifest.json').read_text())
    results = []
    sheet = []
    for ep in manifest['fit']:
        assert members[int(ep.rsplit('-',1)[1])] == 'train'
        receipt = json.loads((SOURCE/ep/'receipt.json').read_text())
        index = json.loads((CACHE/ep/'index.json').read_text())
        assert receipt['split'] == index['split'] == 'train'
        assert sha(SOURCE/ep/'receipt.json') == index['receipt_sha256']
        ledger = rows(SOURCE/ep/'frames.jsonl')
        assert sha(SOURCE/ep/'frames.jsonl') == receipt['files']['frames.jsonl']
        truth = json.loads((STUDY/'runtime/r2'/(ep+'.truth.json')).read_text())
        selected = {len(ledger)-1}
        for e in truth['events']:
            for dt in (0, 5, 20, 60):
                selected.add(next((i for i,l in enumerate(truth['labels']) if l['tick'] >= e['destruction_tick']+dt),len(ledger)-1))
        frames = {}
        with (CACHE/ep/'raw.zst').open('rb') as stream:
            for block in index['blocks']:
                indices = selected.intersection(range(block['start'],block['start']+block['count']))
                if not indices: continue
                offset,size = block['raw.zst']; stream.seek(offset)
                images = decode(stream.read(size),block['count'])
                for i in sorted(indices):
                    image = images[i-block['start']]
                    frames[i] = image
                    cv2.imwrite(str(OUT/f'{ep}-{i}.jpg'),image)
        image = frames[len(ledger)-1]
        thumb = cv2.resize(image,(135,285))
        cv2.putText(thumb,ep.rsplit('-',1)[1],(2,20),cv2.FONT_HERSHEY_SIMPLEX,.35,(0,255,0),1)
        sheet.append(thumb)
        results.append(dict(episode=ep,frames=len(ledger),terminal=receipt['terminal'],last_tick_lo=ledger[-1]['tick_lo'],last_tick_hi=ledger[-1]['tick_hi'],selected_ordinals=sorted(selected),receipt_sha256=sha(SOURCE/ep/'receipt.json'),cache_index_sha256=sha(CACHE/ep/'index.json')))
    cv2.imwrite(str(OUT/'fit-endpoints.jpg'),np.concatenate([np.concatenate(sheet[i:i+8],axis=1) for i in range(0,len(sheet),8)],axis=0))
    (OUT/'fit-availability.json').write_text(json.dumps(dict(fit_only=True,split_sha256=SPLIT_SHA,episodes=results),indent=2)+'\n')
    print('audited',len(results),'fit endpoints',flush=True)

if __name__ == '__main__': main()
