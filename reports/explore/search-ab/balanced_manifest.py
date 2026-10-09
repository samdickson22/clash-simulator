"""Prepare fresh contiguous seed inventory into size-balanced ~100-pair shards."""
import argparse,json,statistics
from collections import defaultdict
from pathlib import Path
from clasher.analysis.loss_review.scheduling import balanced_shards,cost_key
p=argparse.ArgumentParser();p.add_argument('--schedule',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--costs',type=Path,required=True);p.add_argument('--pairs-per-shard',type=int,default=100);a=p.parse_args()
schedule=json.loads(a.schedule.read_text());cases=schedule['cases'];costs=json.loads(a.costs.read_text());pairs=len({c[0] for c in cases});count=(pairs+a.pairs_per_shard-1)//a.pairs_per_shard;groups,loads=balanced_shards(cases,count,costs);a.out.mkdir(parents=True,exist_ok=True);shards=[]
for i,(group,load) in enumerate(zip(groups,loads)):
    folder=a.out/f'b{i:04d}';folder.mkdir(exist_ok=True)
    manifest=dict(schedule,cases=group,checked_seeds=sorted({c[1]+o for c in group for o in (0,100000,100001,100002)}))
    (folder/'case-costs.json').write_text(json.dumps(costs)+'\n')
    (folder/'schedule.json').write_text(json.dumps(manifest)+'\n')
    shards.append(dict(name=folder.name,offset=min(c[0] for c in group),pairs=len({c[0] for c in group}),case_file=True,requested_games=len(group),retained_home_games=0,estimated_seconds=load))
(a.out/'shards.json').write_text(json.dumps(dict(paired_seeds=pairs,shards=shards,estimated_loads=loads,dispatch='seed-cluster LPT; longest-case-first inside each shard'),indent=2)+'\n')
