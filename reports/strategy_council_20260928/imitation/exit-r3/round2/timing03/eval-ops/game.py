"""Frozen r1(b) runner with calibrated R3 hook; no anytime-order replacement."""
import argparse,json,os,resource,sys,time
from pathlib import Path
import numpy as np
import torch
from admission import allowed,context,frozen,sha
from protocol import BASES,stage,arm_list
from proposals import load_student,outputs,rank_actions
from imitation.model.inference import single_features
from imitation.exit_r1.rows import write_json

class TimedPolicy:
    def __init__(self,policy,threshold,check):
        self.base=policy;self.model=policy.model;self.costs=policy.costs;self.threshold=threshold;self.check=check;self.cache=None
    def sample(self,packet,d1,generator=None):
        self.check('fallback',self.threshold is not None)
        if self.threshold is None:return self.base.sample(packet,d1,generator)
        with torch.inference_mode():
            b=single_features(packet,d1,self.costs);p,ranks=outputs(self.model,b)
        mask=packet['action_mask'];order=rank_actions(ranks[0].numpy(),mask)
        action=int(order[0]) if len(order) and float(p[0])>=self.threshold else 2304
        assert mask[action] and action<=2304
        self.cache=(d1,order,mask.copy());return action
    def propose(self,packet,d1,k=8):
        self.check('proposer',self.threshold is not None)
        if self.threshold is None:return self.base.propose(packet,d1,k)
        assert self.cache is not None and self.cache[0] is d1 and np.array_equal(self.cache[2],packet['action_mask'])
        return [dict(action=int(a),slot=int(a)//576,tile=int(a)%576,probability=None) for a in self.cache[1][:k]]

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--lane',choices=tuple(BASES),required=True);p.add_argument('--arm',required=True);p.add_argument('--index',type=int,required=True);p.add_argument('--block',required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args();j=Path(a.job)
    assert allowed(j) and len(os.sched_getaffinity(0))==1;f=frozen(j)
    from journal import record as journal
    journal(j,'game',lane=a.lane,index=a.index,arm=a.arm,smoke=a.smoke)
    b=json.loads(Path(a.block).read_text());assert b['parent_pid']==os.getppid() and b['context']==context() and b['index']==a.index and b['lane']==a.lane and b['smoke']==a.smoke and a.arm in b['arms']
    stage1=json.loads((j/'stage1-results.json').read_text()) if a.lane=='stage2' else None
    assert b['arms']==arm_list(a.lane,stage1)
    steps=f['arms'][a.arm]['steps'] if a.arm!='K0' else None
    ck=j/'fits'/a.arm/f'step-{steps:08d}.pt' if steps else j/'inputs/main02.pt'
    cal=None
    if a.arm!='K0':
        off=json.loads((j/'offline'/f'{a.arm}.json').read_text());c=json.loads((j/'offline'/f'{a.arm}-calibration.json').read_text())
        assert off['stage1_complete'] and off['checkpoint_sha256']==c['checkpoint_sha256']==sha(ck)
        if a.lane=='stage2':assert off['survives']
        else:assert a.arm=='R3a' and not off['survives'],'original kill must remain immutable'
        cal=c['threshold']
    torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False
    from imitation.exit_r1 import screen
    def guard(stop):
        assert allowed(j) and len(os.sched_getaffinity(0))==1,'home admission/STOP changed'
    screen.execution_guard=guard
    runner,policies=screen.initialize(dict(native=str(j/'reporting-native/clasher_core.abi3.so'),checkpoints={'init':str(j/'inputs/main02.pt')}))
    checks=dict(fallback_calls=0,proposer_calls=0,student_fallback_calls=0,student_proposer_calls=0,min_timer_offset_seconds=None)
    def timer(kind,student):
        frame=sys._getframe(1)
        while frame is not None and frame.f_code is not screen.run_case.__code__:frame=frame.f_back
        assert frame is not None and 'begin' in frame.f_locals,'fallback/proposer outside unchanged r1(b) timer'
        offset=time.monotonic()-frame.f_locals['begin'];assert offset>=0
        players=frame.f_locals['players'];assert set(players)=={0,1}
        for v in players.values():assert v.core.arm=='W' and v.core.config.threads==1 and v.core.config.horizon==160 and not v.core.reserve_floor
        checks[kind+'_calls']+=1
        if student:checks['student_'+kind+'_calls']+=1
        old=checks['min_timer_offset_seconds'];checks['min_timer_offset_seconds']=offset if old is None else min(old,offset)
    policies['init']=TimedPolicy(policies['init'],None,timer)
    policies[a.arm]=policies['init'] if a.arm=='K0' else TimedPolicy(load_student(ck,cal),cal,timer)
    base=BASES[a.lane][int(a.smoke)];assert 0<=a.index<(2 if a.smoke else 600)
    folder=j/stage(a.lane,a.smoke)/'cases'
    record=screen.run_case(runner,policies,'fallback',a.arm,a.index,base+a.index,folder,j/'REPORTING.STOP',freeze_sha256=sha(j/'evaluation-freeze.json'))
    assert checks['fallback_calls'] and checks['proposer_calls']
    if a.arm!='K0':assert checks['student_fallback_calls'] and checks['student_proposer_calls']
    record.update(lane=a.lane,never_adoptable=a.lane=='descriptive',adoption_eligible=False,smoke=a.smoke,context=context(),protocol=f['protocol'],deadline_seconds=.2,return_reserve_seconds=.008,threads=1,horizon=160,frozen_runner_sha256=f['files']['eval-source/imitation/exit_r1/screen.py'],native_sha256=f['files']['reporting-native/clasher_core.abi3.so'],checkpoint_sha256=sha(ck),calibration_sha256=sha(j/'offline'/f'{a.arm}-calibration.json') if cal is not None else None,checks=checks,own_deck=a.index%5,opponent_deck=(a.index//5)%5)
    write_json(folder/f'fallback-{a.arm}-{a.index:04d}.json',record)

if __name__=='__main__':
    t=time.monotonic();status='failed'
    try:main();status='complete'
    finally:
        j=Path(sys.argv[sys.argv.index('--job')+1]);u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
        write_json(j/'case-meters'/f'{os.getpid()}.json',dict(pid=os.getpid(),pgid=os.getpgrp(),status=status,parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-t,accounting='Nested in whole pool tree; never sum again'))
