"""Fixed-state OFF receipts and ON replay of the frozen 125 public states."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import pickle
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'reports/explore/w-confirm'), str(ROOT/'src')]
import run


def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['off','on'],required=True)
    p.add_argument('--corpus',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run.initialize();os.sched_setaffinity(0,{60})
    from delay import DelayAwarePlanner
    from clasher.rl.c56_rollout_planner import C56SearchConfig, C56RolloutPlanner
    import clasher_core
    rows=pickle.loads((a.corpus/'states-ready.pkl').read_bytes())
    refs={r['id']:r for r in json.loads((a.corpus/'symmetric-screen-samples.json').read_text())
          if r['variant']=='screen8' and r['repeat']==0}
    records=[];samples=[]
    for row in rows:
        modes=('d0','d27') if a.mode=='off' else ('d27',)
        for mode in modes:
            config=C56SearchConfig(threads=1)
            if a.mode=='on':
                from dataclasses import replace
                config=replace(config,wait_screen8=True)
            cls=C56RolloutPlanner if mode=='d0' else DelayAwarePlanner
            kw=dict(backend='native',seed=row['seed']+100001,native=run.R.native,native_config=run.R.config,config=config)
            if mode=='d27':kw.update(command_delay=27,delay_aware=True)
            core=cls(run.R.builder,run.R.bots,**kw)
            core.rng.bit_generator.state=copy.deepcopy(row['candidate_rng_state'])
            info=copy.deepcopy(row['info']);core.info=info;core.costs=run.R.costs
            t=time.perf_counter();cpu=time.process_time()
            candidates,mask=core.candidates(info.packet);candidates=[x for x in candidates if x!=2305]
            expected=row['candidates'] if a.mode=='on' else [x for x in row['candidates'] if x<2400]
            assert candidates==expected,(row['id'],candidates,expected)
            rng=np.random.default_rng();rng.bit_generator.state=copy.deepcopy(row['root_rng_state'])
            root=run.R.root(info,row['opponent'],rng)
            assert root.digest()==row['root_digest']
            choice=core.score_candidates(root,info.seat,candidates,trace=a.mode=='off')
            elapsed=(time.perf_counter()-t)*1000;cpu_ms=(time.process_time()-cpu)*1000
            if a.mode=='on':
                ref=refs[row['id']];kept=[(x,v) for x,v in zip(candidates,core.last['scores']) if v is not None]
                assert choice==ref['action'],(row['id'],choice,ref['action'])
                assert [x for x,v in kept]==ref['candidates'],row['id']
                assert [v for x,v in kept]==ref['scores'],row['id']
                # Deadline zero admits no partial/late candidate and falls back to WAIT.
                fallback=core.score_candidates(root,info.seat,candidates,deadline=time.monotonic()-1)
                assert fallback==2304 and all(v is None for v in core.last['scores'])
            else:
                record=dict(id=row['id'],mode=mode,candidates=candidates,action=choice,last=core.last)
                records.append(record)
            assert root.digest()==row['root_digest']
            samples.append(dict(id=row['id'],mode=mode,wall_ms=elapsed,cpu_ms=cpu_ms))
        if len(samples)%25==0:print(json.dumps(dict(states=len(samples))),flush=True)
    result=dict(mode=a.mode,states=len(rows),checks=len(samples),
        native=clasher_core.__file__,native_sha256=hashlib.sha256(Path(clasher_core.__file__).read_bytes()).hexdigest(),
        corpus_sha256=hashlib.sha256((a.corpus/'states-ready.pkl').read_bytes()).hexdigest(),
        digest=hashlib.sha256(json.dumps(records,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        exact=True,samples=samples)
    a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)

if __name__=='__main__':main()
