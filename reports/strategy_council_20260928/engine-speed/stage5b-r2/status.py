"""Timing/progress only; never expose interim strength."""
import json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
rows=[json.loads(p.read_text()) for p in (HERE/'confirmation').glob('*.json')]
print('games',len(rows),'/384','complete_pairs',sum(sum(r['pair']==pair for r in rows)==2 for pair in {r['pair'] for r in rows}))
if rows:
    walls=[t[0] for r in rows for t in r['timings']]
    print('decisions',len(walls),'p99',float(np.quantile(walls,.99)),'max',max(walls),'overruns',sum(w>.25 for w in walls),'truncations',sum(r['timing']['truncations'] for r in rows),'fallbacks',sum(r['timing']['fallbacks'] for r in rows))
for i in range(3):
    p=HERE/f'worker{i}.exit';print('worker',i,'exit',p.read_text().strip() if p.exists() else 'not exited')
