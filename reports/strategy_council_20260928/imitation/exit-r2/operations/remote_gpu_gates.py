"""Owned remote admissions/launch/status for scoring and home-only h2h."""
import argparse
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import time
from experiment_x7 import load_experiment
from fit_collection_ready_x7 import snapshot,group_alive
from stage1_gpu_guard import verify_amendment,digest,HOSTS

def utc():return subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
def write(path,d):
    path.parent.mkdir(parents=True,exist_ok=True);p=Path(str(path)+'.tmp');p.write_text(json.dumps(d,indent=2)+'\n');p.replace(path)

def route_admission(job):
    from evaluation_k_yield import admission
    host=socket.gethostname().split('.')[0]
    assert host in ('127x01','127x03')
    if host=='127x01' and not snapshot(job,'X4',4883)['ready']:return dict(admitted=False,host=host,reason='X4 final EMA/clean fit exit pending')
    statepath=job/'stage2-route-g-state.json';state=json.loads(statepath.read_text()) if statepath.exists() else {}
    admitted=admission(job,['stage2 route'],state) and os.getloadavg()[0]<=100
    write(statepath,state)
    return dict(admitted=admitted,host=host,utc=utc(),load1=os.getloadavg()[0],reason='unchanged K release/G drain/home24GiB and X4 clean exit admission')

def attempt_state(job,stage,arm):
    out=job/('offline' if stage==1 else 'stage2');record=out/f'{arm}.json'
    label=f'stage1-{arm}-attempt1' if stage==1 else f'stage2-{arm}-home-attempt1'
    log=job/(label+'.log');identity=Path(str(log)+'.identity.json')
    if not identity.exists():return dict(status='not-started',host=socket.gethostname().split('.')[0])
    pid=json.loads(identity.read_text())['pid'];live=group_alive(pid)
    meters=list(out.glob(f'{arm}-meter-{pid}.json'))
    if live:return dict(status='active',pid=pid,pgid=pid,log=str(log))
    if not meters:return dict(status='failed',pid=pid,reason='attempt exited without meter; retain log and review')
    meter=json.loads(meters[0].read_text())
    good=(meter.get('exit_code')==0 and meter.get('reason') is None) if stage==1 else (not meter['failures'] and meter['completed']==256)
    if not good or not record.exists():return dict(status='failed',pid=pid,meter=meter,reason='attempt did not close a complete scientific result')
    return dict(status='done',pid=pid,pgid=pid,result=json.loads(record.read_text()),meter=meter)

def start(job,stage,arm,cores):
    verify_amendment(job);f=load_experiment(job);state=attempt_state(job,stage,arm)
    assert state['status']=='not-started',state
    if stage==1:
        assert socket.gethostname().split('.')[0]==HOSTS[arm]
        assert snapshot(job,arm,f['arms'][arm]['steps'])['ready']
        module='supervise_stage1_gpu.py';args=['--job',str(job),'--arm',arm];core='126';label=f'stage1-{arm}-attempt1'
    else:
        assert route_admission(job)['admitted'],'home h2h route not yet admitted'
        off=json.loads((job/'offline'/f'{arm}.json').read_text());assert off['survives']
        checkpoint=job/'fits'/arm/f"step-{f['arms'][arm]['steps']:08d}.pt"
        assert digest(checkpoint)==off['checkpoint_sha256']
        assert digest(job/'native/clasher_core.abi3.so')==f['r1_h2h_native_sha256']
        assert cores and set(cores)<=set(range(40 if socket.gethostname().split('.')[0]=='127x01' else 60))
        module='game_pool_x7.py';args=['--job',str(job),'--stage','2','--arm',arm,'--cores',*map(str,cores)];core='63';label=f'stage2-{arm}-home-attempt1'
    command=['bash',str(job/'pilot/detach.sh'),str(job/(label+'.log')),'--cwd',str(job/'source'),'nice','-n','19','chrt','--idle','0','taskset','-c',core,'env',f'PYTHONPATH={job}/ops:{job}/source:{job}/source/src','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','NUMEXPR_NUM_THREADS=1',f'TMPDIR={job}/tmp',f'XDG_CACHE_HOME={job}/cache','PYTHONDONTWRITEBYTECODE=1',str(job/'venv/bin/python'),'-B',str(job/'ops'/module),*args]
    identity=json.loads(subprocess.check_output(command,text=True))
    return dict(status='launched',**identity,log=str(job/(label+'.log')),stage=stage,arm=arm)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',required=True);ap.add_argument('--operation',choices=('admission','status','start'),required=True);ap.add_argument('--stage',type=int,choices=(1,2));ap.add_argument('--arm');ap.add_argument('--cores',type=int,nargs='*',default=[]);a=ap.parse_args();j=Path(a.job)
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getscheduler(0)==os.SCHED_IDLE
    if a.operation=='admission':result=route_admission(j)
    elif a.operation=='status':result=attempt_state(j,a.stage,a.arm)
    else:result=start(j,a.stage,a.arm,a.cores)
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
