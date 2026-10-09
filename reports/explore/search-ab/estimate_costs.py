"""Dispatch estimates use game CPU receipts, excluding external pauses."""
import json,statistics
from pathlib import Path
from collections import defaultdict
from clasher.analysis.loss_review.scheduling import cost_key
root=Path(__file__).resolve().parent;costs=defaultdict(list)
for p in (root/'shards').glob('p*/games/*.json'):
    r=json.loads(p.read_text());m=r['metadata'];case=(0,m['seed'],m['delay_ticks'],m['own_deck'],m['opponent_deck'],m['style'],r['cohort']);costs[cost_key(case)].append(r['cpu_seconds'])
(root/'case-costs.json').write_text(json.dumps({k:statistics.median(v) for k,v in costs.items()},indent=2)+'\n');print(len(costs))
