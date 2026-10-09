"""Tail-cost trade-offs after WAIT-only reductions miss the one-core target."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pickle
import time
import numpy as np
import run
from latency import decision,timing

VARIANTS=['plays1','plays2','all1','all2','plays2wait1','horizon80','horizon100','horizon120']


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    run.initialize();rows=pickle.loads((a.out/'states-ready.pkl').read_bytes());raw=[];results={}
    for mode in ('original','symmetric'):
        reference={s['id']:s for s in json.loads((a.out/f'{mode}-samples.json').read_text())
                   if s['variant']=='full' and s['repeat']==0}
        os.sched_setaffinity(0,{60})
        for name in VARIANTS:decision(mode,rows[0],'native-'+name if mode=='original' else name)
        for repeat in range(3):
            for index,row in enumerate(rows):
                order=VARIANTS if (index+repeat)%2==0 else list(reversed(VARIANTS))
                for name in order:
                    s=decision(mode,row,'native-'+name if mode=='original' else name)
                    s.update(mode=mode,variant=name,repeat=repeat,budget='one core')
                    raw.append(s)
                if index%25==0:print(json.dumps(dict(mode=mode,repeat=repeat,state=index,samples=len(raw))),flush=True)
        results[mode]={}
        for name in VARIANTS:
            samples=[s for s in raw if s['mode']==mode and s['variant']==name]
            unique=[s for s in samples if s['repeat']==0]
            regrets=[]
            for s in unique:
                ref=reference[s['id']];scores=dict(zip(ref['candidates'],ref['scores']))
                regrets.append(max(scores.values())-scores[s['action']])
            results[mode][name]=dict(states=len(unique),agreement_count=sum(s['action']==reference[s['id']]['action'] for s in unique),
                exact_action_agreement=np.mean([s['action']==reference[s['id']]['action'] for s in unique]).item(),
                play_wait_agreement=np.mean([(s['action']<2304)==(reference[s['id']]['action']<2304) for s in unique]).item(),
                exact_score_vectors=sum(s['scores']==reference[s['id']]['scores'] for s in unique),
                mean_reference_regret=float(np.mean(regrets)),max_reference_regret=float(max(regrets)),
                wall=timing([s['wall_ms'] for s in samples]),cpu=timing([s['cpu_ms'] for s in samples]),
                prepare=timing([s['prepare_ms'] for s in samples]),scoring=timing([s['scoring_ms'] for s in samples]),budget='one core')
        (a.out/f'{mode}-extra-samples.json').write_text(json.dumps([s for s in raw if s['mode']==mode])+'\n')
    (a.out/'latency-extra.json').write_text(json.dumps(dict(results=results,variants=VARIANTS,
        state_count=len(rows),repeats=3,scope='latency-only adaptive extension; same fixed states and full references',
        win_rate_claims=False),indent=2)+'\n')
    print(json.dumps(results),flush=True)


if __name__=='__main__':main()
