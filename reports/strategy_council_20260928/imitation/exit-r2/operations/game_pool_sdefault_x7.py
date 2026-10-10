"""All paired arms in shuffled-by-rotation seed blocks, never pre-run controls."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
from imitation.exit_r1.rows import sha,write_json
from stage3_sdefault_admission_x7 import frozen,selection,context,allowed,load_receipt
from evaluation_g_yield import admission

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--cores',type=int,nargs='+',required=True)
    p.add_argument('--smoke',action='store_true');a=p.parse_args();j=Path(a.job);frozen(j);c=context()
    topology=subprocess.check_output(['lscpu','-p=CPU,CORE,SOCKET'],text=True)
    physical={int(s.split(',')[0]):tuple(s.split(',')[1:]) for s in topology.splitlines() if not s.startswith('#')}
    assert len({physical[n] for n in a.cores})==len(a.cores)
    assert set(a.cores)<=set(range(60)), '60-63 reserved for stage1/2; smoke qualification uses core60 via explicit amendment only'
    # No reporting arm/control can run before all seven stage1/2 outcomes exist.
    chosen=['S-standin'] if a.smoke else selection(j)
    assert chosen,'no stage2 survivor'
    arms=['C-v1']+chosen+['K0'];stage=j/('stage3-sdefault-smoke' if a.smoke else 'stage3-sdefault')
    stage.mkdir(exist_ok=True);(stage/'blocks').mkdir(exist_ok=True);(stage/'logs').mkdir(exist_ok=True)
    lock=(stage/'POOL.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if not a.smoke:
        qual=json.loads((j/'sdefault-wrapper-qualification.json').read_text())
        assert qual['passed'] and qual['harness_sha256']==sha(j/'stage3-sdefault-addendum.json')
    write_json(stage/'selection.json',dict(arms=arms,selected=chosen,smoke=a.smoke,
        rule='lowest stage2 loss, highest stage1 hard agreement, X1-X6; max3',
        harness_sha256=sha(j/'stage3-sdefault-addendum.json')))
    pending=[];complete=[]
    for i in ((4,5) if a.smoke else range(600)):
        block=stage/'blocks'/f'{i:04d}.json'
        if block.exists():
            r=json.loads(block.read_text())
            assert r['complete'] and r['arms']==arms and r['harness_sha256']==sha(j/'stage3-sdefault-addendum.json')
            for case in r['cases']:
                assert sha(stage/'cases'/f"sdefault-{case['arm']}-{i:04d}.json")==case['sha256']
            complete.append(i)
        else:pending.append(i)
    active={};state={};failures=[];started=time.monotonic();minimum=1<<62;stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True;(j/'REPORTING.STOP').touch()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        while pending or active:
            if stopping or (j/'REPORTING.STOP').exists() or time.time()>=1791696000:raise InterruptedError('owned STOP/deadline')
            load=load_receipt();minimum=min(minimum,load['mem_available_bytes'])
            for core in list(active):
                child,index,stream=active[core];rc=child.poll()
                if rc is None:continue
                stream.close();del active[core]
                if rc:
                    failures.append(dict(index=index,exit_code=rc));raise RuntimeError('paired block failed; incomplete cases excluded')
                complete.append(index)
            admitted=allowed(j) and admission(j,['S-default seed blocks'],state)
            for core in a.cores:
                if core in active or not pending or not admitted or load['load1']>100:continue
                i=pending.pop(0);stream=(stage/'logs'/f'block-{i:04d}-attempt-{os.getpid()}.log').open('w')
                command=['taskset','-c',str(core),sys.executable,'-B',str(j/'ops/stage3_block_worker_x7.py'),
                         '--job',str(j),'--index',str(i),'--arms',*arms]
                if a.smoke:command.append('--smoke')
                # Isolated owned group lets STOP terminate only this block and its games.
                active[core]=(subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True),i,stream)
            write_json(stage/'progress.json',dict(completed=len(complete),pending=len(pending),
                active={str(core):dict(pid=v[0].pid,index=v[1]) for core,v in active.items()},
                arms=arms,admitted=admitted,load=load,failures=failures))
            time.sleep(1)
    finally:
        for child,_,stream in active.values():
            child.terminate() # Block handler reaps its case before exiting.
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait()
            stream.close()
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
        write_json(stage/f'pool-meter-{os.getpid()}.json',dict(host=c['host'],arms=arms,completed=len(complete),failures=failures,
            parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,
            wall_seconds=time.monotonic()-started,min_available_bytes=minimum,
            accounting='Whole pool tree includes blocks and games, including replay/failed attempts. Do not add nested meters.'))
    assert len(complete)==(2 if a.smoke else 600)

if __name__=='__main__':main()
