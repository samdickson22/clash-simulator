"""Smoke: LivePerception on raw 540x1140 validation frames (original cache raw.zst), prints records."""
import json, sys
from pathlib import Path
import numpy as np
import common as C
from infer import LivePerception

export, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 40
guard = C.HeldoutGuard(); ep = [e for e in guard.episodes('validation') if (C.CACHE/e/'raw.zst').exists()][0]
idx = json.loads((C.CACHE/ep/'index.json').read_text())
from pixel_cache import decompress, RAW
import dense_labels as D
lab = D.load(Path('/mpac/sdicks02/jobs/clasher/live-perception-20261014/labels')/f'{ep}.npz')
p = LivePerception(export, device='cpu'); out = []
import time; t0 = time.perf_counter()
for k in range(20, 20+n//8):
    b = idx['blocks'][k]; off, size = b['raw.zst']
    with (C.CACHE/ep/'raw.zst').open('rb') as f:
        f.seek(off); rows = decompress(f.read(size), (b['count'], int(np.prod(RAW))))
    for j in range(0, b['count'], 2):
        i = k*16+j; rec = p.step(rows[j].reshape(RAW), float(lab['tick'][i])*50.)
        out.append(rec)
dt = (time.perf_counter()-t0)/len(out)
print(json.dumps(dict(frames=len(out), ms_per_frame_cpu=round(dt*1000, 1), events=sum(len(r['events']) for r in out))))
print(json.dumps(out[-1])[:1500])
