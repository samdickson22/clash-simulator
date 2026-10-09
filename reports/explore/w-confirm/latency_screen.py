"""Coarse scan / full refinement, using the same fixed state references."""
import argparse
import json
import os
from pathlib import Path
import pickle
import numpy as np
import run
from latency import decision,timing

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    run.initialize();rows=pickle.loads((a.out/'states-ready.pkl').read_bytes());raw=[];results={}
    for mode in ('original','symmetric'):
        reference={s['id']:s for s in json.loads((a.out/f'{mode}-samples.json').read_text()) if s['variant']=='full' and s['repeat']==0}
        names=['paired-full','screen3','screen5','screen8'];os.sched_setaffinity(0,{60})
        def variant(name):
            name='full' if name=='paired-full' else name
            return 'native-'+name if mode=='original' else name
        for name in names:decision(mode,rows[0],variant(name))
        for repeat in range(3):
            for index,row in enumerate(rows):
                for name in (names if (index+repeat)%2==0 else names[::-1]):
                    s=decision(mode,row,variant(name))
                    s.update(mode=mode,variant=name,repeat=repeat,budget='one core');raw.append(s)
                if index%25==0:print(json.dumps(dict(mode=mode,repeat=repeat,state=index,samples=len(raw))),flush=True)
        results[mode]={}
        for name in names:
            samples=[s for s in raw if s['mode']==mode and s['variant']==name];unique=[s for s in samples if s['repeat']==0]
            regrets=[];refined_exact=0
            for s in unique:
                ref=reference[s['id']];scores=dict(zip(ref['candidates'],ref['scores']))
                assert all(scores[a]==v for a,v in zip(s['candidates'],s['scores'])),(mode,name,s['id'])
                refined_exact+=1;regrets.append(max(scores.values())-scores[s['action']])
            results[mode][name]=dict(states=len(unique),agreement_count=sum(s['action']==reference[s['id']]['action'] for s in unique),
                exact_action_agreement=np.mean([s['action']==reference[s['id']]['action'] for s in unique]).item(),
                play_wait_agreement=np.mean([(s['action']<2304)==(reference[s['id']]['action']<2304) for s in unique]).item(),
                refined_scores_exact_states=refined_exact,mean_reference_regret=float(np.mean(regrets)),max_reference_regret=float(max(regrets)),
                wall=timing([s['wall_ms'] for s in samples]),cpu=timing([s['cpu_ms'] for s in samples]),
                prepare=timing([s['prepare_ms'] for s in samples]),scoring=timing([s['scoring_ms'] for s in samples]),budget='one core')
        (a.out/f'{mode}-screen-samples.json').write_text(json.dumps([s for s in raw if s['mode']==mode])+'\n')
    (a.out/'latency-screen.json').write_text(json.dumps(dict(results=results,state_count=len(rows),repeats=3,
        all_initial_candidates_scanned=True,waits_full_scored=True,win_rate_claims=False),indent=2)+'\n')
    print(json.dumps(results),flush=True)

if __name__=='__main__':main()
