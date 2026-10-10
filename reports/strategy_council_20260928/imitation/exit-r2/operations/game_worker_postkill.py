"""One S-default game; only the seed-block runner may admit a case."""
import argparse
import json
import os
from pathlib import Path
import resource
import time
from imitation.exit_r1.rows import sha,write_json as original_write_json
from postkill_admission import labelled
def write_json(path,value):original_write_json(path,labelled(value))
from experiment_x7 import load_experiment
from postkill_admission import frozen,selection,context,allowed,BASE,SMOKE_BASE

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--arm',required=True)
    p.add_argument('--index',type=int,required=True);p.add_argument('--block',required=True);p.add_argument('--smoke',action='store_true')
    a=p.parse_args();j=Path(a.job);c=context();assert len(c['affinity'])==1 and allowed(j)
    h=frozen(j);block=json.loads(Path(a.block).read_text())
    assert block['parent_pid']==os.getppid() and block['context']==c
    assert block['index']==a.index and block['smoke']==a.smoke and a.arm in block['arms']
    assert block['harness_sha256']==sha(j/'postkill-sdefault-addendum.json')
    f=load_experiment(j);checkpoints={'init':str(j/'inputs/main02.pt')}
    if a.smoke:
        assert a.index in (4,5) and block['arms']==['C-v1','S-standin','K0']
        checkpoints['S-standin']=checkpoints['init']
        base=SMOKE_BASE
    else:
        assert 0<=a.index<600
        chosen=selection(j);assert chosen and block['arms']==['C-v1']+chosen+['K0']
        qual=json.loads((j/'postkill-wrapper-qualification.json').read_text())
        assert qual['passed'] and qual['harness_sha256']==sha(j/'postkill-sdefault-addendum.json')
        if a.arm in chosen:
            off=json.loads((j/'offline'/f'{a.arm}.json').read_text())
            checkpoints[a.arm]=str(j/'fits'/a.arm/f"step-{f['arms'][a.arm]['steps']:08d}.pt")
            assert sha(checkpoints[a.arm])==off['checkpoint_sha256']
        base=BASE
    assert sha(checkpoints['init'])==f['init_sha256']
    import k_postkill_sdefault as adapter
    checks=dict(timer_calls=0,student_calls=0,legal_proposals=0,min_inference_offset_seconds=None)
    if a.smoke:
        import sdefault
        original_choice=sdefault.student_choice;original_poll=adapter.poll_before_search
        def timer():
            frame=__import__('sys')._getframe(1)
            while frame is not None and not (frame.f_code.co_name=='run_game' and 'wall0' in frame.f_locals):frame=frame.f_back
            assert frame is not None,'Inference outside K wall0 timer'
            offset=time.monotonic()-frame.f_locals['wall0'];assert offset>=0
            assert frame.f_locals['deadline_seconds']==.2
            assert frame.f_globals['OPTIONS']['return_reserve_seconds']==.008
            assert set(frame.f_locals['players'])=={a.index%2}
            for actor,policy in frame.f_locals['policies'].items():
                assert policy.player.policy is frame.f_globals['POLICY'],'Both v1 polling actors must retain released v1'
            core=frame.f_locals['players'][a.index%2].core
            assert core.search_threads==1 and core.coarse_horizon==160
            assert core.arm==('0' if a.arm=='K0' else 'W')
            minimum=checks['min_inference_offset_seconds']
            checks['min_inference_offset_seconds']=offset if minimum is None else min(minimum,offset)
            checks['timer_calls']+=1
        def choice(policy,packet,mask,d1):
            timer();action,order=original_choice(policy,packet,mask,d1)
            assert mask[action] and action<=2304 and len(set(order))==len(order)
            assert all(p<2304 and mask[p] for p in order)
            checks['student_calls']+=1;checks['legal_proposals']+=len(order)
            return action,order
        def poll(*args):
            timer();return original_poll(*args)
        sdefault.student_choice=choice;adapter.poll_before_search=poll
    adapter.run_case(j,a.arm,a.index,base+a.index,checkpoints,h,smoke=a.smoke)
    if a.smoke:
        assert checks['timer_calls']>0
        if a.arm=='S-standin':assert checks['student_calls']>0
        write_json(j/'postkill-sdefault-smoke'/f'checks-{a.arm}-{a.index:04d}.json',checks)

if __name__=='__main__':
    started=time.monotonic();status='failed'
    try:main();status='complete'
    finally:
        j=Path(__import__('sys').argv[__import__('sys').argv.index('--job')+1])
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
        write_json(j/('postkill-sdefault-smoke' if '--smoke' in __import__('sys').argv else 'postkill-sdefault')/f'case-meter-{os.getpid()}.json',dict(status=status,
            parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,
            wall_seconds=time.monotonic()-started,
            accounting='Nested in block/pool whole-tree CPU; do not add again.'))
