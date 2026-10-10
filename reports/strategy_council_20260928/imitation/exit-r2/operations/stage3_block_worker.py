"""Every arm of one paired seed runs back to back on one physical core."""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
from imitation.exit_r1.rows import sha,write_json
from stage3_sdefault_admission import frozen,context,allowed,load_receipt,arm_order

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--index',type=int,required=True)
    p.add_argument('--arms',nargs='+',required=True);p.add_argument('--smoke',action='store_true')
    a=p.parse_args();j=Path(a.job);frozen(j);c=context();assert len(c['affinity'])==1
    assert allowed(j),'K timing games, stop/deadline or home memory floor'
    stage=j/('stage3-sdefault-smoke' if a.smoke else 'stage3-sdefault')
    stage.mkdir(exist_ok=True);blocks=stage/'blocks';blocks.mkdir(exist_ok=True)
    cases=stage/'cases';cases.mkdir(exist_ok=True);logs=stage/'logs';logs.mkdir(exist_ok=True)
    identity=blocks/f'{a.index:04d}-attempt-{os.getpid()}.json'
    # Partial prior blocks are never mixed with this block's later host load.
    archive=stage/'abandoned'/f'{a.index:04d}-before-{os.getpid()}'
    for arm in a.arms:
        old=cases/f'sdefault-{arm}-{a.index:04d}.json'
        if old.exists():
            archive.mkdir(parents=True,exist_ok=True);old.rename(archive/old.name)
        raw=stage/'k-raw'/arm/'games'/f'sim-{a.index:04d}-d27-{arm}.json'
        if raw.exists():
            archive.mkdir(parents=True,exist_ok=True);raw.rename(archive/f'raw-{arm}.json')
    request=dict(parent_pid=os.getpid(),context=c,index=a.index,smoke=a.smoke,arms=a.arms,
                 arm_order=arm_order(a.arms,a.index),harness_sha256=sha(j/'stage3-sdefault-addendum.json'),
                 start=load_receipt(),cases=[],complete=False)
    write_json(identity,request)
    stopping=False;child=None
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        for arm in request['arm_order']:
            assert not stopping and allowed(j),'admission changed during paired block; abandon whole block'
            command=[sys.executable,'-B',str(j/'ops/game_worker_sdefault.py'),'--job',str(j),
                     '--arm',arm,'--index',str(a.index),'--block',str(identity)]
            if a.smoke:command.append('--smoke')
            path=logs/f'{arm}-{a.index:04d}-attempt-{os.getpid()}.log'
            before=load_receipt()
            with path.open('w') as stream:
                child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT)
                while child.poll() is None:
                    if stopping or not allowed(j):raise InterruptedError('paired block admission changed')
                    time.sleep(1)
                assert child.returncode==0,'case failed'
                child=None
            case=cases/f'sdefault-{arm}-{a.index:04d}.json'
            r=json.loads(case.read_text())
            assert r['terminal'] and r['search_ab']['worker_affinity']==c['affinity']
            assert r['search_ab']['host'].split('.')[0]==c['host']
            request['cases'].append(dict(arm=arm,sha256=sha(case),before=before,after=load_receipt()))
            write_json(identity,request)
    finally:
        if child is not None:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        # Reap games before block exit so pool accounting includes their CPU.
    request['complete']=True;request['end']=load_receipt()
    write_json(identity,request);write_json(blocks/f'{a.index:04d}.json',request)

if __name__=='__main__':
    started=time.monotonic();status='failed'
    try:main();status='complete'
    finally:
        j=Path(sys.argv[sys.argv.index('--job')+1]);u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
        write_json(j/'stage3-sdefault'/f'block-meter-{os.getpid()}.json',dict(status=status,
            parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,
            wall_seconds=time.monotonic()-started,
            accounting='Includes game children; nested in pool total, never add child/block meters again.'))
