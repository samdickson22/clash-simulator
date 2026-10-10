"""Frozen125 states: exact search, same-packet cache, RNG and student timing."""
import argparse,copy,hashlib,json,os,pickle,subprocess,time
from pathlib import Path
import numpy as np
import torch
import run
from cached_policy import CachedPolicy
from proposals import outputs,rank_actions

def utc():return subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--corpus',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    assert os.uname().nodename=='127x01' and os.sched_getaffinity(0)<={0,1,2}
    native=run.initialize()
    from delay import DelayAwarePlanner
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    from imitation.evaluation.standalone import StandalonePlayer
    from imitation.evaluation.d1 import model_packet
    import planner,anchor
    from gc_window import WINDOW
    cfg=json.loads((Path(__file__).parent/'plan.json').read_text())
    rows=pickle.loads((a.corpus/'states-ready.pkl').read_bytes())
    refs={r['id']:r for r in json.loads((a.corpus/'symmetric-screen-samples.json').read_text()) if r['variant']=='screen8' and r['repeat']==0}
    counts=dict(coarse_frozen=0,anchor_frozen=0,v1_cache_action_rng=0,v1_cache_proposals=0,student_cache_equal=0,proposal_augmented_frozen=0,root_immutable=0,student_charged_inside_timer=0)
    records=[]
    for row in rows:
        rng=np.random.default_rng();rng.bit_generator.state=copy.deepcopy(row['root_rng_state'])
        root=run.R.root(copy.deepcopy(row['info']),row['opponent'],rng)
        assert root.digest()==row['root_digest']
        def construct(cls,threads=1):
            c=cls(DelayAwarePlanner)(run.R.builder,run.R.bots,backend='native',native=run.R.native,native_config=run.R.config,catalog=run.CAT,config=C56SearchConfig(threads=1,wait_screen8=False),seed=row['seed']+100001,command_delay=27,delay_aware=True,symmetric_opponent=True,opponent_delay=27,opponent_interval=10,opponent_capacity=1,max_outstanding=1,arm='W',variant='screen8',**dict(search_threads=threads,coarse_horizon=160))
            c.rng.bit_generator.state=copy.deepcopy(row['candidate_rng_state']);c.info=copy.deepcopy(row['info']);c.costs=run.R.costs
            return c
        for label,cls,threads in [('coarse',planner.planner_class,1),('anchor',anchor.planner_class,2)]:
            c=construct(cls,threads);candidates,_=c.candidates(c.info.packet);candidates=[x for x in candidates if x!=2305]
            action=c.score_candidates(root,c.info.seat,candidates);c.close()
            ref=refs[row['id']]
            assert action==ref['action'] and c.last['candidates']==ref['candidates'] and c.last['scores']==ref['scores'],(row['id'],label)
            counts[label+'_frozen']+=1
        info=row['info'];order=list(info.own['hand'])+list(info.own['cycle'])
        original=StandalonePlayer(run.POLICY,run.R.builder,run.R.costs,info.seat,order,row['seed']+271828+info.seat)
        cached=CachedPolicy(run.POLICY);single=StandalonePlayer(cached,run.R.builder,run.R.costs,info.seat,order,row['seed']+271828+info.seat)
        for tick in (info.tick,info.tick+5):
            old,mask=original.decide(tick,info.packet,[]);new,mask2=single.decide(tick,info.packet,[])
            assert old==new and np.array_equal(mask,mask2)
            assert torch.equal(original.generator.get_state(),single.generator.get_state())
            packet=model_packet(info.packet,mask)
            props=run.POLICY.propose(packet,original.last_d1,8)
            cached_props=cached.propose(packet,single.last_d1,8)
            assert props==cached_props
        assert cached.forward_calls==cached.fallback_calls==2 and cached.proposal_calls==2
        counts['v1_cache_action_rng']+=1;counts['v1_cache_proposals']+=1
        student_begin=None;seen=[]
        def timing():
            assert student_begin is not None and time.monotonic()>=student_begin and WINDOW.active
            seen.append(time.monotonic()-student_begin)
        student=CachedPolicy(run.STUDENT,cfg['student']['threshold'],timing)
        with WINDOW:
            student_begin=time.monotonic()
            d1=original.last_d1
            choice=student.sample(packet,d1)
            student_props=student.propose(packet,d1)
            charged=time.monotonic()-student_begin
        assert len(seen)==2 and charged>0 and student.forward_calls==1
        from reference_timed_policy import TimedPolicy
        reference=TimedPolicy(run.STUDENT,cfg['student']['threshold'],lambda *args:None)
        expected=reference.sample(packet,d1)
        expected_props=reference.propose(packet,d1,8)
        assert choice==expected and student_props==expected_props
        counts['student_cache_equal']+=1;counts['student_charged_inside_timer']+=1
        for props in (cached_props,student_props):
            c=construct(planner.planner_class);ca,_=c.candidates(c.info.packet,[p['action'] for p in props]);ca=[x for x in ca if x!=2305]
            action=c.score_candidates(root,c.info.seat,ca)
            # Frozen no-deadline scorer on identical augmented candidates.
            old=construct(planner.planner_class)
            expected=planner.e1.frozen.planner_class(DelayAwarePlanner).score_candidates(old,root,c.info.seat,ca)
            assert action==expected and c.last==old.last
        counts['proposal_augmented_frozen']+=1
        try:run.R.native.rollout_e1(root,info.seat,2304,'balanced',27,27,160,10,1.,0.)
        except TimeoutError:pass
        else:raise AssertionError('zero native budget admitted')
        assert root.digest()==row['root_digest'];counts['root_immutable']+=1
        records.append(dict(id=row['id'],charged_student_seconds=charged,callback_offsets=seen))
        if len(records)%25==0:print(json.dumps(counts),flush=True)
    assert len(rows)==125 and all(v==125 for v in counts.values())
    result=dict(utc=utc(),states=125,counts=counts,records=records,native_sha256=sha(Path(native)),checkpoint_sha256=cfg['student']['checkpoint_sha256'],corpus_sha256={f:sha(a.corpus/f) for f in ('states-ready.pkl','symmetric-screen-samples.json')})
    a.out.write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
