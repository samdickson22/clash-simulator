"""Fit-host GPU stage1 immediately; one admitted home01/03 stage2 pool."""
import argparse
import json
import os
from pathlib import Path
import resource
import shlex
import socket
import subprocess
import time
from experiment_x7 import load_experiment
from fit_collection_ready_x7 import collection_ready
from stage1_gpu_guard import HOSTS,verify_amendment,digest

def write(path,d):
    path.parent.mkdir(parents=True,exist_ok=True);p=Path(str(path)+'.tmp');p.write_text(json.dumps(d,indent=2)+'\n');p.replace(path)
def remote(job,host,operation,stage=None,arm=None,cores=()):
    cmd=['nice','-n','19','chrt','--idle','0','taskset','-c','63','env',f'PYTHONPATH={job}/ops:{job}/source:{job}/source/src','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',str(job/'venv/bin/python'),'-B',str(job/'ops/remote_gpu_gates.py'),'--job',str(job),'--operation',operation]
    if stage:cmd+=['--stage',str(stage),'--arm',arm]
    if cores:cmd+=['--cores',*map(str,cores)]
    r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5',host,shlex.join(cmd)],capture_output=True,text=True)
    if r.returncode:raise RuntimeError(f'{host} {operation} {stage}/{arm}: {r.stderr[-2000:]} {r.stdout[-2000:]}')
    return json.loads(r.stdout)

def stage2_prepare(job,arm,home):
    f=load_experiment(job);host=HOSTS[arm];step=f['arms'][arm]['steps'];target=job/'fits'/arm
    remote_mkdir=shlex.join(['mkdir','-p',str(target),str(job/'offline'),str(job/'stage2'),str(job/'logs')])
    subprocess.run(['ssh',home,remote_mkdir],check=True)
    if home!=host:
        # Direct source-host -> evaluation-home LAN transfer, never via05.
        files=[target/f'step-{step:08d}.pt',target/'inputs.json',target/'runtime.json',target/'complete.json',target/'segment.json']
        cmd=['nice','-n','19','chrt','--idle','0','taskset','-c','126','rsync','-a','--bwlimit=153600','--rsync-path=nice -n 19 chrt --idle 0 taskset -c 63 rsync',*[str(p) for p in files],home+':'+str(target)+'/']
        subprocess.run(['ssh',host,shlex.join(cmd)],check=True)
    if home!='127x03':
        subprocess.run(['scp',str(job/'offline'/f'{arm}.json'),home+':'+str(job/'offline')+'/'],check=True)

def existing_stage2(job,arm):
    found=[]
    for host in ('127x01','127x03'):
        state=remote(job,host,'status',2,arm)
        if state['status']!='not-started':found.append((host,state))
    assert len(found)<=1,'duplicate remote stage2 identities: stop admission and review'
    return found[0] if found else None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',required=True);a=ap.parse_args();j=Path(a.job);start=time.monotonic();failures=[];priority=False;active=None;last=0
    assert socket.gethostname().split('.')[0]=='127x03'
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getscheduler(0)==os.SCHED_IDLE
    verify_amendment(j);f=load_experiment(j)
    launch_state=j/'gpu-gates-launches.json';launched=json.loads(launch_state.read_text()) if launch_state.exists() else {'offline':{},'stage2':{}}
    try:
        while not (j/'CONTROLLER.STOP').exists() and time.time()<1791696000:
            if not priority:
                reply=subprocess.run(['ssh','-o','ConnectTimeout=5','127x08','cat '+str(j/'X3-health.json')],capture_output=True,text=True)
                if reply.returncode==0 and json.loads(reply.stdout).get('reason'):
                    replies=[subprocess.run(['ssh',host,'touch '+str(j/'X3.RESUME.REQUEST')]) for host in ('127x13','127x14')];priority=all(r.returncode==0 for r in replies)
            for arm,host in HOSTS.items():
                if (j/'offline'/f'{arm}.json').exists():continue
                state=remote(j,host,'status',1,arm)
                if state['status']=='done':
                    write(j/'offline'/f'{arm}.json',state['result']);write(j/'offline'/f'{arm}-remote-meter.json',dict(host=host,**state['meter']));continue
                if state['status']=='failed':raise RuntimeError(f'offline {arm} failed: {state}')
                if state['status']=='active':continue
                if not collection_ready(j,arm,host,f['arms'][arm]['steps']):continue
                state=remote(j,host,'start',1,arm);launched['offline'][arm]=dict(host=host,**state);write(launch_state,launched)
            if active:
                arm,home=active;state=remote(j,home,'status',2,arm)
                if state['status']=='failed':raise RuntimeError(f'stage2 {arm} failed: {state}')
                if state['status']=='done':
                    write(j/'stage2'/f'{arm}.json',state['result']);write(j/'stage2'/f'{arm}-remote-meter.json',dict(host=home,**state['meter']))
                    if home!='127x03':
                        # Preserve raw case/game attempts and all nested CPU meters; charge pool whole CPU once.
                        subprocess.run(['rsync','-a','--bwlimit=153600','--rsync-path=nice -n 19 chrt --idle 0 taskset -c 63 rsync',home+':'+str(j/'stage2')+'/',str(j/'stage2')+'/'],check=True)
                    active=None
            if active is None:
                for arm in HOSTS:
                    off=j/'offline'/f'{arm}.json'
                    if not off.exists() or not json.loads(off.read_text())['survives'] or (j/'stage2'/f'{arm}.json').exists():continue
                    old=launched['stage2'].get(arm)
                    if old:
                        state=remote(j,old['host'],'status',2,arm)
                        if state['status']=='failed':raise RuntimeError(f'existing stage2 attempt failed: {state}')
                        assert state['status']!='not-started','lost stage2 launch receipt; review rather than duplicate'
                        active=(arm,old['host']);break
                    previous=existing_stage2(j,arm)
                    if previous:
                        home,state=previous
                        if state['status']=='failed':raise RuntimeError(f'existing uncollected stage2 failure: {state}')
                        launched['stage2'][arm]=dict(host=home,pid=state['pid'],pgid=state['pid'],adopted_existing=True);write(launch_state,launched);active=(arm,home);break
                    #01 admitted only after X4 clean exit;03 only after explicit K release.
                    home=next((host for host in ('127x01','127x03') if remote(j,host,'admission')['admitted']),None)
                    if not home:continue
                    stage2_prepare(j,arm,home)
                    state=remote(j,home,'start',2,arm,range(24 if home=='127x01' else 32));launched['stage2'][arm]=dict(host=home,**state);write(launch_state,launched);active=(arm,home);break
            offline={arm:json.loads((j/'offline'/f'{arm}.json').read_text()) for arm in HOSTS if (j/'offline'/f'{arm}.json').exists()}
            stage2={arm:json.loads((j/'stage2'/f'{arm}.json').read_text()) for arm in HOSTS if (j/'stage2'/f'{arm}.json').exists()}
            complete=len(offline)==7 and all(not d['survives'] or arm in stage2 for arm,d in offline.items())
            if time.monotonic()-last>30 or complete:
                write(j/'controller.json',dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),stage='stages1-2 complete' if complete else 'fit-host GPU stage1; conditional admitted home stage2',offline=offline,stage2=stage2,active=['stage2',*active] if active else None,offline_active=[arm for arm in launched['offline'] if arm not in offline],failures=failures,x3_priority_requested=priority,wall_seconds=time.monotonic()-start));last=time.monotonic()
            if complete:break
            time.sleep(15)
    except Exception as e:
        failures.append(str(e));raise
    finally:
        own=resource.getrusage(resource.RUSAGE_SELF);kids=resource.getrusage(resource.RUSAGE_CHILDREN)
        write(j/f'controller-meter-{os.getpid()}.json',dict(parent_cpu_seconds=own.ru_utime+own.ru_stime,child_cpu_seconds=kids.ru_utime+kids.ru_stime,wall_seconds=time.monotonic()-start,failures=failures,note='Controller SSH/local metadata children only. Remote stage1 supervisors and stage2 pools are separately whole-metered; no nested child CPU added twice.'))

if __name__=='__main__':main()
