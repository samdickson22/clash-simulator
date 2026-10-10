"""No game seeds: 125 synthetic roots and injected-clock S-default qualification."""
import argparse,copy,importlib.util,json,os,pickle,resource,subprocess,sys,time
from pathlib import Path
import numpy as np
from imitation.exit_r1.rows import sha,write_json
from imitation.exit_r1.screen import load_student

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);a=p.parse_args();j=Path(a.job)
    assert __import__('socket').gethostname().split('.')[0]=='127x03'
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getscheduler(0)==os.SCHED_IDLE
    assert os.sched_getaffinity(0)=={60}
    from evaluation_g_yield import admission
    state={}
    while not admission(j,['S-default qualification'],state):time.sleep(1)
    kdir=j/'source/reports/explore/k-anytime'
    os.environ['CLASHER_DELAY_NATIVE_DIR']=str(j/'k-native')
    sys.path[:0]=[str(kdir),str(j/'source/reports/explore/e1')]
    import planner
    spec=importlib.util.spec_from_file_location('x_sdefault_qual_k',kdir/'run.py')
    k=importlib.util.module_from_spec(spec);spec.loader.exec_module(k);k.initialize()
    from delay import DelayAwarePlanner
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    from imitation.evaluation.d1 import D1Tracker
    from sdefault import student_choice,select_default
    policy=load_student(j/'inputs/main02.pt')
    corpus=Path('/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/latency')
    pins={'states-ready.pkl':'8b188918b95cf6c79f0db0639beaff2e80526ce11c146cdfe0edb0bb8e6f3cce',
          'symmetric-screen-samples.json':'86ecbb600b712d0fab05c2022e8d95d1dfb47a9be531ed4b8722a1acdcfd2b7d'}
    for name,digest in pins.items():assert sha(corpus/name)==digest
    rows=pickle.loads((corpus/'states-ready.pkl').read_bytes())
    refs={r['id']:r for r in json.loads((corpus/'symmetric-screen-samples.json').read_text()) if r['variant']=='screen8' and r['repeat']==0}
    from imitation.exit_r1 import emitter
    emitter.PRIOR=k.PRIOR;fill_deck=emitter.decks()[0]
    counts={'C-v1':0,'S-standin':0};score_counts=dict(counts)
    empty_hook_matches=dict(counts);samples=[];failures=[]
    def make_core(row):
        core=planner.planner_class(DelayAwarePlanner)(k.R.builder,k.R.bots,backend='native',native=k.R.native,native_config=k.R.config,catalog=k.CAT,
            config=C56SearchConfig(threads=1,wait_screen8=False),seed=row['seed']+100001,command_delay=27,delay_aware=True,
            symmetric_opponent=True,opponent_delay=27,opponent_interval=10,opponent_capacity=1,max_outstanding=1,
            arm='W',variant='screen8',search_threads=1,coarse_horizon=160)
        core.rng.bit_generator.state=copy.deepcopy(row['candidate_rng_state'])
        core.info=copy.deepcopy(row['info']);core.costs=k.R.costs
        return core
    for row in rows:
        rng=np.random.default_rng();rng.bit_generator.state=copy.deepcopy(row['root_rng_state'])
        root=k.R.root(copy.deepcopy(row['info']),row['opponent'],rng)
        assert root.digest()==row['root_digest']
        for arm in ('C-v1','S-standin'):
            core=make_core(row)
            candidates,mask=core.candidates(core.info.packet)
            if arm=='S-standin':
                own=row['info'].own
                order=[];seen=set()
                for name in own['hand']+own['cycle']+list(fill_deck):
                    token=k.R.builder.token_id(name,namespace='card_action') if name else 0
                    if token>1 and token not in seen:
                        seen.add(token);order.append(name)
                    if len(order)==8:break
                assert len(order)==8
                tracker=D1Tracker(k.R.builder,k.R.costs,row['info'].seat,order)
                default,order=student_choice(policy,core.info.packet,mask,tracker.update(row['info'].tick,[]))
                core.coarse_order=order;core.refine_proposals=order[:8]
                core.rng.bit_generator.state=copy.deepcopy(row['candidate_rng_state'])
                candidates,_=core.candidates(core.info.packet,core.refine_proposals)
            else:default=2304
            candidates=[c for c in candidates if c!=2305]
            action=core.score_candidates(root,core.info.seat,candidates,deadline=None,fallback=default)
            action=select_default(core,action,default,'v1_polled' if arm=='C-v1' else 'student_argmax',None)
            empty_ref=refs[row['id']];empty_hook_matches[arm]+=int(action==empty_ref['action'])
            if arm=='S-standin':
                # Compare the default layer with untouched K1 using identical
                # hooks and the exact candidate list. Hook effects are allowed.
                reference=make_core(row)
                reference.coarse_order=core.coarse_order
                reference.refine_proposals=core.refine_proposals
                reference_action=reference.score_candidates(root,reference.info.seat,list(candidates),deadline=None,fallback=default)
                ref=dict(action=reference_action,candidates=list(reference.last['candidates']),scores=list(reference.last['scores']))
                reference.close()
            else:ref=empty_ref
            matched=action==ref['action'];counts[arm]+=int(matched)
            scores_match=core.last['candidates']==ref['candidates'] and core.last['scores']==ref['scores']
            score_counts[arm]+=int(scores_match)
            if not matched or not scores_match:failures.append(dict(id=row['id'],arm=arm,action=action,reference=ref['action'],scores_match=scores_match))
            assert not core.deadline_stats['default_used'] and root.digest()==row['root_digest']
            samples.append(dict(id=row['id'],arm=arm,action=action,reference_action=ref['action'],matched=matched,
                scores_match=scores_match,empty_hook_action=empty_ref['action'],hook_action_changed=action!=empty_ref['action']))
            core.close()
        if len(samples)%50==0:print(json.dumps(counts),flush=True)
    import pytest
    clock_rc=pytest.main(['-q','-p','no:cacheprovider',str(j/'ops/test_sdefault.py')])
    passed=len(rows)==125 and all(v==125 for v in counts.values()) and all(v==125 for v in score_counts.values()) and clock_rc==0
    write_json(j/'sdefault-qualification.json',dict(passed=passed,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),
        states=len(rows),counts=counts,score_counts=score_counts,empty_hook_matches=empty_hook_matches,
        hook_action_change_rate=(len(rows)-empty_hook_matches['S-standin'])/len(rows),
        equivalence='C-v1 vs empty-hook K1; S-n vs K1 with same student hooks and candidate list. Full package contrast does not separate hook/default effects.',
        failures=failures,samples=samples,clock_tests_exit=clock_rc,corpus_sha256=pins,
        native_sha256=sha(j/'k-native/clasher_core.abi3.so'),standin_policy_sha256=sha(j/'inputs/main02.pt'),
        standin_context='Synthetic fixture current own HUD known distinct token hand+cycle, filled to8 from fixed first train-archetype deck, initializes D1; no outcome/heldout input. Reporting uses exact opening order.',
        no_game_seeds_consumed=True,files={name:sha(j/'ops'/name) for name in ('sdefault.py','k_stage3_sdefault.py','test_sdefault.py','qualify_sdefault.py')}))
    if not passed:raise SystemExit(1)

if __name__=='__main__':
    started=time.monotonic();status='failed'
    try:main();status='passed'
    finally:
        j=Path(sys.argv[sys.argv.index('--job')+1]);u=resource.getrusage(resource.RUSAGE_SELF);c=resource.getrusage(resource.RUSAGE_CHILDREN)
        write_json(j/f'sdefault-qualification-meter-{os.getpid()}.json',dict(status=status,
            parent_cpu_seconds=u.ru_utime+u.ru_stime,child_cpu_seconds=c.ru_utime+c.ru_stime,wall_seconds=time.monotonic()-started))
