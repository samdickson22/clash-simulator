"""Decompose search-call outcomes by candidate count (4 == WAIT + three timed waits only)."""
import json,sys
from collections import Counter
from pathlib import Path
import numpy as np
root=Path(sys.argv[1]);out={}
for arm in ('K0','R3a'):
    D=[];T=[]
    for i in range(600):
        r=json.loads((root/f'fallback-{arm}-{i:04d}.json').read_text());s=r['stats'][r['seat']]
        D+=s['deadlines']
    n=len(D);triv=[d for d in D if d['candidates']<=4 and not d['hit']]
    nontriv=[d for d in D if not (d['candidates']<=4 and not d['hit'])]
    full=[d for d in D if not d['hit']]
    coarse_done_cut=[d for d in D if d['hit'] and not d['fallback']]
    out[arm]=dict(calls=n,trivial_no_play_calls=len(triv),trivial_share=len(triv)/n,trivial_completed=sum(d['completed'] for d in triv),
        nontrivial_calls=len(nontriv),nontrivial_completed=sum(d['completed'] for d in nontriv),nontrivial_completed_per_call=sum(d['completed'] for d in nontriv)/len(nontriv),
        nontrivial_fallback_rate=sum(d['fallback'] for d in nontriv)/len(nontriv),
        full_search_calls=len(full),coarse_done_but_cut=len(coarse_done_cut),fallback_calls=sum(d['fallback'] for d in D),
        precutoff_fallbacks=sum(d['fallback'] and d['completed']==0 and d['wall_seconds']<.19 for d in D),
        fallback_cand_hist=dict(sorted(Counter(d['candidates'] for d in D if d['fallback']).items())),
        nohit_cand_hist=dict(sorted(Counter(d['candidates'] for d in D if not d['hit']).items())))
print(json.dumps(out,indent=1))
