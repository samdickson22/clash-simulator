"""Detached home03 fit collection, stage1 diagnostics and conditional stage2."""
import argparse
from experiment_x6 import load_experiment
from evaluation_k_yield import admission
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import time
from imitation.exit_r1.rows import sha,write_json

ARMS={'X1':'127x09','X2':'127x16','X3':'127x08','X4':'127x01','X5':'127x04','X6':'127x13'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);a=p.parse_args();j=Path(a.job)
    assert socket.gethostname().split('.')[0]=='127x03'
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getscheduler(0)==os.SCHED_IDLE
    assert json.loads((j/'seed-audit.json').read_text())['passed']
    active=None;log=None;last=0;started=time.monotonic();failures=[];priority_requested=False;g_state={}
    while True:
        if time.time()>=1791696000 or (j/'CONTROLLER.STOP').exists():break
        # Only X-owned stop/health metadata: X3 resume has priority over X6.
        if not priority_requested:
            response=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5','127x08',
                'cat '+str(j/'X3-health.json')],capture_output=True,text=True)
            if response.returncode==0 and json.loads(response.stdout).get('reason'):
                yielded=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5','127x13',
                    'touch '+str(j/'X3.RESUME.REQUEST')])
                priority_requested=yielded.returncode==0
        if active is not None and active.poll() is not None:
            rc=active.returncode;log.close();active=None
            if rc:failures.append(dict(task=task,exit_code=rc));break
        if active is None:
            for arm,host in ARMS.items():
                if (j/'offline'/f'{arm}.json').exists():continue
                step=load_experiment(j)['arms'][arm]['steps']
                remote=j/'fits'/arm;local=j/'fits'/arm
                response=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5',host,
                    'test -f '+str(remote/'complete.json')+' && cat '+str(remote/'complete.json')],
                    capture_output=True,text=True)
                if response.returncode:continue
                done=json.loads(response.stdout)
                if done['stopped'] or done['step']!=step:continue
                if not admission(j,['offline',arm],g_state):continue
                local.mkdir(parents=True,exist_ok=True)
                files=[remote/f'step-{step:08d}.pt',remote/'inputs.json',remote/'complete.json',remote/'segment.json',remote/'runtime.json']
                subprocess.run(['rsync','-a','--bwlimit=153600','--rsync-path=nice -n 10 rsync',
                    *[host+':'+str(f) for f in files],str(local)+'/'],check=True)
                remote_sha=subprocess.check_output(['ssh',host,'sha256sum '+str(remote/f'step-{step:08d}.pt')],text=True).split()[0]
                assert sha(local/f'step-{step:08d}.pt')==remote_sha
                task=['offline',arm]
                (j/'logs').mkdir(exist_ok=True);log=(j/'logs'/f'offline-{arm}.log').open('a')
                active=subprocess.Popen(['taskset','-c','60',sys.executable,'-B',str(j/'ops/offline_x6.py'),
                    '--job',str(j),'--arm',arm,'--checkpoint',str(local/f'step-{step:08d}.pt')],stdout=log,stderr=subprocess.STDOUT)
                break
        if active is None:
            for arm in ARMS:
                offline=j/'offline'/f'{arm}.json'
                if not offline.exists() or not json.loads(offline.read_text())['survives'] or (j/'stage2'/f'{arm}.json').exists():continue
                if not admission(j,['stage2',arm],g_state):continue
                task=['stage2',arm];log=(j/'logs'/f'stage2-{arm}.log').open('a')
                active=subprocess.Popen([sys.executable,'-B',str(j/'ops/game_pool_x6.py'),'--job',str(j),
                    '--stage','2','--arm',arm,'--cores','60','61','62','63'],stdout=log,stderr=subprocess.STDOUT)
                break
        offline={arm:json.loads((j/'offline'/f'{arm}.json').read_text()) for arm in ARMS if (j/'offline'/f'{arm}.json').exists()}
        stage2={arm:json.loads((j/'stage2'/f'{arm}.json').read_text()) for arm in ARMS if (j/'stage2'/f'{arm}.json').exists()}
        complete=len(offline)==len(ARMS) and all(not v['survives'] or arm in stage2 for arm,v in offline.items())
        status='waiting for fits / stage1 / conditional stage2'
        if complete:
            status=('stages1-2 complete; DAgger eligible; stage3 HELD' if (j/'STAGE3.HOLD').exists() else 'stages1-2 complete; stage3 and DAgger eligible') if any(v['survives'] for v in stage2.values()) else 'complete: every arm killed before DAgger'
        if time.monotonic()-last>30 or complete:
            write_json(j/'controller.json',dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),
                stage=status,offline=offline,stage2=stage2,active=task if active else None,
                failures=failures,x3_priority_requested=priority_requested,wall_seconds=time.monotonic()-started))
            last=time.monotonic()
        if complete:break
        time.sleep(15)
    usage=resource.getrusage(resource.RUSAGE_SELF);kids=resource.getrusage(resource.RUSAGE_CHILDREN)
    write_json(j/f'controller-meter-{os.getpid()}.json',dict(parent_cpu_seconds=usage.ru_utime+usage.ru_stime,
        child_cpu_seconds=kids.ru_utime+kids.ru_stime,wall_seconds=time.monotonic()-started,failures=failures))
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
