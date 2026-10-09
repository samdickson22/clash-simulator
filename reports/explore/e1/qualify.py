"""No games: frozen public corpus and same-state v1 byte/action equality."""
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
sys.path[:0] = [str(ROOT/'src'),str(Path(__file__).parent),str(ROOT/'reports/explore/w-confirm')]
import importlib.util
rspec=importlib.util.spec_from_file_location('e1_reference_run',ROOT/'reports/explore/w-confirm/run.py')
reference_run=importlib.util.module_from_spec(rspec);rspec.loader.exec_module(reference_run)
sys.path.insert(0,str(Path(__file__).parent))
from planner import planner_class, frozen


def equal(a,b):
    assert set(a) == set(b)
    for k in a:
        x,y=np.asarray(a[k]),np.asarray(b[k])
        assert x.dtype==y.dtype and x.shape==y.shape and x.tobytes()==y.tobytes(),k


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--corpus',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();reference_run.initialize();r=reference_run.R;cat=reference_run.CAT
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    from delay import DelayAwarePlanner
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    from imitation.model import load_policy
    from imitation.model.features import build_row
    from imitation.evaluation.standalone import StandalonePlayer
    from imitation.evaluation.d1 import model_packet
    from policy import V1Policy
    cfg=json.loads((Path(__file__).parent/'config.json').read_text())
    checkpoint=Path(cfg['policy']['checkpoint'])
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==cfg['policy']['checkpoint_sha256']
    policy=load_policy(checkpoint)
    rows=pickle.loads((a.corpus/'states-ready.pkl').read_bytes())
    refs={r['id']:r for r in json.loads((a.corpus/'symmetric-screen-samples.json').read_text()) if r['variant']=='screen8' and r['repeat']==0}
    digest=hashlib.sha256();wchecks=0;vchecks=0;native_checks=0
    openings={}
    for row in rows:
        if row['seed'] not in openings:
            openings[row['seed']]=list(row['info'].own['hand'])+list(row['info'].own['cycle'])
        def construct(cls,arm):
            c=cls(DelayAwarePlanner)(r.builder,r.bots,backend='native',native=r.native,native_config=r.config,
                catalog=cat,config=C56SearchConfig(threads=1,wait_screen8=False),seed=row['seed']+100001,
                command_delay=27,delay_aware=True,symmetric_opponent=True,opponent_delay=27,opponent_interval=10,
                opponent_capacity=1,max_outstanding=1,arm=arm,variant='screen8' if arm=='W' else 'full')
            c.rng.bit_generator.state=copy.deepcopy(row['candidate_rng_state']);c.info=copy.deepcopy(row['info']);c.costs=r.costs
            return c
        c=construct(planner_class,'0')
        rng=np.random.default_rng();rng.bit_generator.state=copy.deepcopy(row['root_rng_state'])
        root=r.root(c.info,row['opponent'],rng);before=root.digest();assert before==row['root_digest']
        candidates,_=c.candidates(c.info.packet);candidates=[x for x in candidates if x!=2305]
        # E1 flagOFF+deadlineOFF must exactly delegate the frozen symmetric scorer.
        action=c.score_candidates(root,c.info.seat,candidates,trace=True)
        old=construct(frozen.planner_class,'0');ca,_=old.candidates(old.info.packet);ca=[x for x in ca if x!=2305]
        assert candidates==ca and action==old.score_candidates(root,c.info.seat,ca,trace=True) and c.last==old.last
        digest.update(json.dumps(c.last,sort_keys=True).encode())
        w=construct(planner_class,'W');wc,_=w.candidates(w.info.packet);wc=[x for x in wc if x!=2305]
        wa=w.score_candidates(root,w.info.seat,wc);ref=refs[row['id']]
        assert wa==ref['action'] and w.last['candidates']==ref['candidates'] and w.last['scores']==ref['scores'],row['id']
        wchecks+=1
        # Native cancellation cannot mutate a public hypothetical root.
        try: r.native.rollout_e1(root,c.info.seat,2304,'balanced',27,27,160,10,1.,0.)
        except TimeoutError: pass
        else: raise AssertionError('zero native budget admitted')
        assert root.digest()==before;native_checks+=1
        order=openings[row['seed']]
        seed=row['seed']+271828+c.info.seat
        actual=V1Policy(policy,r.builder,r.costs,c.info.seat,order,seed)
        gate=StandalonePlayer(policy,r.builder,r.costs,c.info.seat,order,seed)
        for tick in (c.info.tick,c.info.tick+5):
            choice=actual.poll(tick,c.info.packet,[])
            expected,mask=gate.decide(tick,c.info.packet,[])
            assert choice==expected and actual.mask.tobytes()==mask.tobytes()
            equal(actual.player.last_d1,gate.last_d1)
            equal(model_packet(c.info.packet,actual.mask),model_packet(c.info.packet,mask))
            equal(build_row(model_packet(c.info.packet,actual.mask),actual.player.last_d1,policy.costs),
                build_row(model_packet(c.info.packet,mask),gate.last_d1,policy.costs))
            vchecks+=1
        if wchecks%25==0:print(json.dumps(dict(states=wchecks)),flush=True)
    result=dict(states=len(rows),symmetric_off_exact=len(rows),w_screen8_exact=wchecks,
                native_zero_budget_immutable=native_checks,v1_byte_action_equal=vchecks,symmetric_off_digest=digest.hexdigest(),
                checkpoint_sha256=cfg['policy']['checkpoint_sha256'],reserve_floor_default=False,
                gate_adapter_sha256={f:hashlib.sha256((ROOT/'imitation/evaluation'/f).read_bytes()).hexdigest()
                                     for f in ('standalone.py','d1.py','events.py')})
    a.out.write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
