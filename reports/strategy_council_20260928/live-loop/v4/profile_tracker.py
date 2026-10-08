"""Fleet-only profile of frozen public development inputs (no outcome scoring)."""
import cProfile
import gzip
import json
from pathlib import Path
import pstats
import sys
from types import SimpleNamespace
from clasher.live.loading import COUNCIL, tracker_class
from clasher.live.belief import StratifiedRng
import numpy as np

base = COUNCIL/'search-noise-s4'
data = json.loads(gzip.decompress((base/'dev-traces/000.json.gz').read_bytes()))
prior = json.loads((base/'runtime/support/human_deck_catalog.json').read_text())
cls = tracker_class()
if '--fast' in sys.argv:
    from clasher.live.tracker import TrackerV3
    cls = TrackerV3
t = cls(prior, data['costs'], body_cards=data['body_cards'], recall=.9, precision=.9)
rng = np.random.default_rng(123)
p = cProfile.Profile()
p.enable()
count = 0
for row in data['rows']:
    if row['seat'] != 0 or row['variant'] != 'T2-N90':
        continue
    t.update_public(row['tick'], [SimpleNamespace(**e) for e in row['events']], row['bodies'])
    d = t.distribution()
    for i in range(4):
        t.sample(StratifiedRng(rng, i, 4, d['concentrated']))
    count += 1
    if count == 1000:
        break
p.disable()
pstats.Stats(p).sort_stats('tottime').print_stats(30)
