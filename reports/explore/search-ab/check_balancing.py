"""Scheduling replay only; no simulator work and no new game outcomes."""
import json
from pathlib import Path
from clasher.analysis.loss_review.scheduling import balanced_shards,cost_key,longest_first
root=Path(__file__).resolve().parent;costs=json.loads((root/'case-costs.json').read_text());cases=[]
for path in sorted((root/'shards').glob('p*/schedule.json')):cases.extend(json.loads(path.read_text())['cases'])
shards,loads=balanced_shards(cases,20,costs);assigned=[c for group in shards for c in group]
assert sorted(map(str,assigned))==sorted(map(str,cases)) and len(cases)==8000
owners={}
for lane,group in enumerate(shards):
    for c in group:
        assert owners.setdefault(c[0],lane)==lane
result=dict(games=len(cases),seed_clusters=len(owners),shards=20,pairs_per_shard=[len({c[0] for c in g}) for g in shards],estimated_cpu_loads=loads,max_min_load_ratio=max(loads)/min(loads),matched_inventory=True,seed_clusters_kept_together=True,scope='deterministic LPT schedule replay, no fresh outcomes')
(root/'receipts/balancing-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
