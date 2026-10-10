"""Load R3 calibration/head into byte-frozen X S-default timer and runner."""
import argparse,importlib.util,json,os,resource,socket,subprocess,sys,time
from pathlib import Path
from exit_r3.rows import sha,write_json
from proposals import load_student,student_choice
from admission import allowed,context


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--arm',required=True);p.add_argument('--index',type=int,required=True);p.add_argument('--block',required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args();j=Path(a.job)
    assert allowed(j) and len(os.sched_getaffinity(0))==1
    block=json.loads(Path(a.block).read_text());assert block['parent_pid']==os.getppid() and block['context']==context() and block['index']==a.index and a.arm in block['arms'] and block['smoke']==a.smoke
    h=json.loads((j/'stage3-sdefault-addendum.json').read_text());assert h['kind']=='S-default-K1'
    for name in ('sdefault.py','k_stage3_sdefault.py'):
        assert sha(j/'frozen-x'/name)==h['files']['ops/'+name]
    sys.path.insert(0,str(j/'frozen-x'))
    import sdefault,k_stage3_sdefault as adapter
    f=json.loads((j/'freeze.json').read_text());checkpoints={'init':str(j/'inputs/main02.pt')};calibrations={}
    for arm in block['arms']:
        if arm in ('C-v1','K0'):continue
        off=json.loads((j/'offline'/f'{arm}.json').read_text())
        if not a.smoke:assert off['stage1_complete'] and off['survives']
        path=j/'fits'/arm/'step-00002500.pt';cal=json.loads((j/'offline'/f'{arm}-calibration.json').read_text())
        assert sha(path)==cal['checkpoint_sha256']==off['checkpoint_sha256']
        checkpoints[arm]=str(path);calibrations[str(path)]=cal['threshold']
    assert sha(checkpoints['init'])==f['files']['inputs/main02.pt']
    baseline_loader=adapter.load_student
    adapter.load_student=lambda path:load_student(path,calibrations[str(path)]) if str(path) in calibrations else baseline_loader(path)
    checks=dict(timer_calls=0,student_calls=0,legal_proposals=0,min_inference_offset_seconds=None)
    def timer():
        frame=sys._getframe(1)
        while frame and not (frame.f_code.co_name=='run_game' and 'wall0' in frame.f_locals):frame=frame.f_back
        assert frame is not None,'R3 inference outside frozen full-decision timer'
        offset=time.monotonic()-frame.f_locals['wall0'];assert offset>=0
        assert frame.f_locals['deadline_seconds']==.2 and frame.f_globals['OPTIONS']['return_reserve_seconds']==.008
        assert set(frame.f_locals['players'])=={a.index%2}
        for actor,policy in frame.f_locals['policies'].items():assert policy.player.policy is frame.f_globals['POLICY']
        core=frame.f_locals['players'][a.index%2].core
        assert core.search_threads==1 and core.coarse_horizon==160 and core.arm==('0' if a.arm=='K0' else 'W')
        old=checks['min_inference_offset_seconds'];checks['min_inference_offset_seconds']=offset if old is None else min(old,offset);checks['timer_calls']+=1
    def choice(*args):
        if a.smoke:timer()
        action,order=student_choice(*args)
        if a.smoke:
            mask=args[2];assert mask[action] and action<=2304 and len(set(order))==len(order) and all(v<2304 and mask[v] for v in order)
            checks['student_calls']+=1;checks['legal_proposals']+=len(order)
        return action,order
    sdefault.student_choice=choice
    if a.smoke:
        original=adapter.poll_before_search
        def poll(*args):timer();return original(*args)
        adapter.poll_before_search=poll
    base=4503601917370496 if a.smoke else 4503601907370496
    assert 0<=a.index<(8 if a.smoke else 600)
    adapter.run_case(j,a.arm,a.index,base+a.index,checkpoints,h,smoke=a.smoke)
    stage=j/('stage3-sdefault-smoke' if a.smoke else 'stage3-sdefault');path=stage/'cases'/f'sdefault-{a.arm}-{a.index:04d}.json';case=json.loads(path.read_text())
    raw=stage/'k-raw'/a.arm/'games'/f'sim-{a.index:04d}-d27-{a.arm}.json';record=json.loads(raw.read_text())
    # The frozen X adapter labels its historical class IDLE. Correct provenance
    # to coordinator's requested actual OTHER; search/game behavior untouched.
    for obj in (record['metadata'],case):obj.update(scheduler='SCHED_OTHER',nice=10)
    record['metadata']['r3_default']='calibrated_gate_then_ranked_play' if a.arm not in ('C-v1','K0') else case['default_source']
    write_json(raw,record)
    case.update(raw_game_sha256=sha(raw),stage=2,r3_adapter_sha256=sha(Path(__file__)),r3_proposals_sha256=sha(Path(__file__).with_name('proposals.py')),smoke_checks=checks if a.smoke else None,calibration_sha256=sha(j/'offline'/f'{a.arm}-calibration.json') if a.arm not in ('C-v1','K0') else None,r3_default=record['metadata']['r3_default'])
    assert case['seed']==base+a.index and case['terminal'] and case['threads']==1 and case['coarse_horizon']==160
    assert case['search_ab']['host'].split('.')[0]==context()['host'] and case['search_ab']['worker_affinity']==context()['affinity']
    if a.smoke:
        assert checks['timer_calls']>0
        if a.arm not in ('C-v1','K0'):assert checks['student_calls']>0
    write_json(path,case)

if __name__=='__main__':
    started=time.monotonic();status='failed'
    try:main();status='complete'
    finally:
        j=Path(sys.argv[sys.argv.index('--job')+1]);u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
        write_json(j/'stage2'/f'case-meter-{os.getpid()}.json',dict(status=status,parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-started,accounting='Nested in whole pool meter; never add this again.'))
