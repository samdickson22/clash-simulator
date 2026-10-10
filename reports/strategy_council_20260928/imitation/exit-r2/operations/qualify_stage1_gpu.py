"""Synthetic float32 CPU/CUDA diagnostic parity, no game or heldout outcome."""
import argparse
import copy
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import time
import numpy as np
import torch
from imitation.exit_r1.screen import load_student
from supplement import teacher
from supplement_gpu import teacher_gpu
from stage1_gpu_guard import digest

class SyntheticStore:
    def __init__(self):
        rng=np.random.default_rng(2026101009);n=128;width=63
        self.b={'ids':torch.from_numpy(rng.integers(1,360,(n,width))),
                'types':torch.from_numpy(rng.integers(1,19,(n,width))),
                'numeric':torch.from_numpy(rng.normal(size=(n,width,24)).astype(np.float32)),
                'valid':torch.ones(n,width,dtype=torch.bool),
                'action_mask':torch.ones(n,2306,dtype=torch.bool)}
        self.b['action_mask'][:,-1]=False
        self.actions=torch.tensor([0 if i%2 else 2304 for i in range(n)])
        self.arrays={'expert_action_supervision_valid':np.ones(n,bool),'teacher_wait_kind':np.zeros(n,int),
                     'teacher_root':np.arange(n)<64,'episode_ids':np.arange(n)%64}
    def batch(self,take):return {k:v[take] for k,v in self.b.items()},{'action':self.actions[take]}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',required=True);a=ap.parse_args();j=Path(a.job)
    assert socket.gethostname().split('.')[0]=='127x01'
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getscheduler(0)==os.SCHED_IDLE
    assert os.sched_getaffinity(0)=={63};start=time.monotonic()
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    available=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())*2**20
    assert available>=8*2**30
    cpu=load_student(j/'inputs/main02.pt');gpu=copy.deepcopy(cpu);gpu.model.to('cuda').eval();store=SyntheticStore();samples=[]
    with torch.inference_mode():
        for begin in (0,64):
            b,_=store.batch(np.arange(begin,begin+64));a0=cpu.model.log_policy(b);a1={k:v.cpu() for k,v in gpu.model.log_policy({k:v.cuda() for k,v in b.items()}).items()}
            errors={}
            for k in a0:
                finite=torch.isfinite(a0[k]);assert torch.equal(finite,torch.isfinite(a1[k]));errors[k]=float((a0[k][finite]-a1[k][finite]).abs().max())
                assert errors[k]<2e-5,(k,errors[k])
            for k in ('gate',):assert torch.equal(a0[k].argmax(1),a1[k].argmax(1))
            q0=(a0['card'][:,:,None]+a0['tile']).flatten(1);q1=(a1['card'][:,:,None]+a1['tile']).flatten(1)
            assert torch.equal(q0.argmax(1),q1.argmax(1));assert torch.equal(q0.topk(8,dim=1).indices,q1.topk(8,dim=1).indices)
            samples.append(errors)
    metrics=[]
    for roots in (True,False):
        c=teacher(cpu,store,roots);g=teacher_gpu(gpu,store,roots)
        assert c['games']==g['games']==64 and c['rows']==g['rows']
        maximum=0.
        for k,v in c['metrics'].items():
            error=abs(v['value']-g['metrics'][k]['value']);maximum=max(maximum,error);assert error<1e-6,(k,error)
            assert np.max(np.abs(np.array(v['ci95'])-np.array(g['metrics'][k]['ci95'])))<1e-6,k
        metrics.append(dict(root_only=roots,rows=c['rows'],maximum_metric_difference=maximum))
    torch.cuda.synchronize();own=resource.getrusage(resource.RUSAGE_SELF);kids=resource.getrusage(resource.RUSAGE_CHILDREN)
    result=dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),passed=True,host='127x01',synthetic_rows=128,games_consumed=0,heldout_rows_consumed=0,log_policy_errors=samples,metrics=metrics,hard_and_top8_exact=True,precision='float32, TF32 off, no autocast',torch=torch.__version__,numpy=np.__version__,parent_cpu_seconds=own.ru_utime+own.ru_stime,children_cpu_seconds=kids.ru_utime+kids.ru_stime,gpu_wall_seconds=time.monotonic()-start,files={n:digest(j/'ops'/n) for n in ['supplement_gpu.py','offline_gpu.py','stage1_gpu_guard.py','supervise_stage1_gpu.py']},scope='Synthetic random valid tensors with v1 EMA; home01 core63 nice19/SCHED_IDLE/Torch1, brief concurrent GPU qualification with unchanged X4 fit; not scientific heldout inference.')
    (j/f'stage1-gpu-qualification-{os.getpid()}.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

if __name__=='__main__':main()
