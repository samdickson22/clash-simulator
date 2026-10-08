"""Inspect >10ms updates in public development replay; fleet only."""
import gzip,json,time,cProfile,pstats
import numpy as np
from types import SimpleNamespace
from clasher.live.loading import COUNCIL
from clasher.live.tracker import TrackerV3
from clasher.live.belief import StratifiedRng
base=COUNCIL/'search-noise-s4'
data=json.loads(gzip.decompress((base/'dev-traces/000.json.gz').read_bytes()))
prior=json.loads((base/'runtime/support/human_deck_catalog.json').read_text())
trackers={}
p=cProfile.Profile();p.enable()
for row in data['rows'][:1200]:
    key=(row['seat'],row['variant'])
    if key not in trackers:
        q,r={'T2-N90':(.9,.9),'T2-N97':(.97,.97),'T2-N64':(180/280,180/270)}[key[1]]
        trackers[key]=(TrackerV3(prior,data['costs'],body_cards=data['body_cards'],recall=q,precision=r),np.random.default_rng(6108))
    t,rng=trackers[key]
    begin=time.perf_counter()
    t.update_public(row['tick'],[SimpleNamespace(**e) for e in row['events']],row['bodies'])
    updated=time.perf_counter();d=t.distribution();dist=time.perf_counter()
    for j in range(4):t.sample(StratifiedRng(rng,j,4,d['concentrated']))
    end=time.perf_counter()
    if end-begin>.02:print(key,row['tick'],[(x-y)*1000 for x,y in ((updated,begin),(dist,updated),(end,dist))],len(row['events']),flush=True)
p.disable();pstats.Stats(p).sort_stats('tottime').print_stats(30)
