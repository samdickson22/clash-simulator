"""Replay frozen125 synthetic public states; no reporting or heldout input."""
import argparse,copy,hashlib,json,os,pickle,subprocess,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(Path(__file__).parent),str(ROOT/'reports/explore/e1')]
from planner import planner_class
import run


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--corpus',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();native=run.initialize()
    from delay import DelayAwarePlanner
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    rows=pickle.loads((a.corpus/'states-ready.pkl').read_bytes())
    refs={r['id']:r for r in json.loads((a.corpus/'symmetric-screen-samples.json').read_text()) if r['variant']=='screen8' and r['repeat']==0}
    counts=dict(K1=0,K4=0,one_four_identical=0,K4h_agreement=0,native_zero_budget_immutable=0)
    samples=[]
    for row in rows:
        rng=np.random.default_rng();rng.bit_generator.state=copy.deepcopy(row['root_rng_state'])
        root=run.R.root(copy.deepcopy(row['info']),row['opponent'],rng)
        assert root.digest()==row['root_digest']
        results={}
        for arm,threads,horizon in [('K1',1,160),('K4',4,160)]:
            c=planner_class(DelayAwarePlanner)(run.R.builder,run.R.bots,backend='native',native=run.R.native,native_config=run.R.config,catalog=run.CAT,
                config=C56SearchConfig(threads=1,wait_screen8=False),seed=row['seed']+100001,command_delay=27,delay_aware=True,
                symmetric_opponent=True,opponent_delay=27,opponent_interval=10,opponent_capacity=1,max_outstanding=1,
                arm='W',variant='screen8',search_threads=threads,coarse_horizon=horizon)
            c.rng.bit_generator.state=copy.deepcopy(row['candidate_rng_state']);c.info=copy.deepcopy(row['info']);c.costs=run.R.costs
            candidates,_=c.candidates(c.info.packet);candidates=[x for x in candidates if x!=2305]
            t=time.monotonic();action=c.score_candidates(root,c.info.seat,candidates);elapsed=time.monotonic()-t;c.close()
            ref=refs[row['id']]
            results[arm]=(action,c.last)
            if arm!='K4h':
                assert action==ref['action'] and c.last['candidates']==ref['candidates'] and c.last['scores']==ref['scores'],(row['id'],arm,c.last,ref)
                counts[arm]+=1
            else: counts['K4h_agreement']+=action==ref['action']
            samples.append(dict(id=row['id'],arm=arm,action=action,reference_action=ref['action'],wall_seconds=elapsed,score_sha256=hashlib.sha256(json.dumps(c.last,sort_keys=True).encode()).hexdigest()))
        assert results['K1']==results['K4'];counts['one_four_identical']+=1
        try: run.R.native.rollout_e1(root,row['info'].seat,2304,'balanced',27,27,160,10,1.,0.)
        except TimeoutError: pass
        else: raise AssertionError('zero budget admitted')
        assert root.digest()==row['root_digest'];counts['native_zero_budget_immutable']+=1
        if counts['K1']%25==0:print(json.dumps(counts),flush=True)
    assert len(rows)==125
    result=dict(qualified_at_utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),states=125,counts=counts,samples=samples,
                native_path=native,native_sha256=hashlib.sha256(Path(native).read_bytes()).hexdigest(),corpus_sha256={f:hashlib.sha256((a.corpus/f).read_bytes()).hexdigest() for f in ('states-ready.pkl','symmetric-screen-samples.json')})
    a.out.write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
