"""Resumable explicit case identities on nonoverlapping physical home cores."""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import socket
import subprocess
import sys
import time
from imitation.exit_r1.rows import write_json,sha
from imitation.exit_r1.screen_metrics import paired_interval

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--stage',type=int,required=True)
    p.add_argument('--arm',required=True);p.add_argument('--cores',type=int,nargs='+',required=True)
    a=p.parse_args();j=Path(a.job);host=socket.gethostname().split('.')[0]
    assert host in ('127x01','127x03') and os.sched_getscheduler(0)==os.SCHED_IDLE
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    topology=subprocess.check_output(['lscpu','-p=CPU,CORE,SOCKET'],text=True)
    physical={int(s.split(',')[0]):tuple(s.split(',')[1:]) for s in topology.splitlines() if not s.startswith('#')}
    assert len({physical[c] for c in a.cores})==len(a.cores)
    stage=j/f'stage{a.stage}';cases=stage/'cases';cases.mkdir(parents=True,exist_ok=True)
    logs=stage/'logs';logs.mkdir(exist_ok=True)
    mode='h2h' if a.stage==2 else 'fallback';count=256 if a.stage==2 else 600
    base=4503601507370496 if a.stage==2 else 4503601517370496
    audit=json.loads((j/'seed-audit.json').read_text());assert audit['passed']
    pending=[];valid=[]
    for i in range(count):
        f=cases/f'{mode}-{a.arm}-{i:04d}.json'
        if f.exists():
            r=json.loads(f.read_text())
            assert (r['mode'],r['arm'],r['index'],r['seed'],r['terminal'],r['freeze_sha256'])==(
                mode,a.arm,i,base+i,True,sha(j/'freeze.json'))
            valid.append(r)
        else:pending.append(i)
    active={};failures=[];start=time.monotonic();minimum=1<<62
    stop=j/'REPORTING.STOP'
    signal.signal(signal.SIGTERM,lambda *_:stop.touch())
    signal.signal(signal.SIGINT,lambda *_:stop.touch())
    try:
        while pending or active:
            if stop.exists():raise InterruptedError('owned reporting STOP')
            available=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024
            minimum=min(minimum,available)
            if available<24*2**30:raise RuntimeError('home memory floor')
            if time.time()>=1791696000:raise RuntimeError('05:20Z completion deadline')
            load=os.getloadavg()[0]
            for core in list(active):
                child,index,stream=active[core]
                rc=child.poll()
                if rc is None:continue
                stream.close();del active[core]
                if rc:failures.append(dict(index=index,exit_code=rc));raise RuntimeError('case worker failed')
                valid.append(json.loads((cases/f'{mode}-{a.arm}-{index:04d}.json').read_text()))
            for core in a.cores:
                if core in active or not pending or load>100:continue
                i=pending.pop(0);stream=(logs/f'{mode}-{a.arm}-{i:04d}.log').open('a')
                command=['taskset','-c',str(core),sys.executable,'-B',str(j/'ops/game_worker.py'),
                    '--job',str(j),'--stage',str(a.stage),'--arm',a.arm,'--index',str(i)]
                active[core]=(subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT),i,stream)
            write_json(stage/f'{a.arm}-progress.json',dict(completed=len(valid),active=len(active),pending=len(pending),load1=load,failures=failures))
            time.sleep(1)
    finally:
        for child,_,stream in active.values():
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
            stream.close()
        own=resource.getrusage(resource.RUSAGE_SELF);kids=resource.getrusage(resource.RUSAGE_CHILDREN)
        write_json(stage/f'{a.arm}-meter-{os.getpid()}.json',dict(host=host,arm=a.arm,stage=a.stage,
            manager_cpu_seconds=own.ru_utime+own.ru_stime,children_cpu_seconds=kids.ru_utime+kids.ru_stime,
            wall_seconds=time.monotonic()-start,completed=len(valid),failures=failures,min_available_bytes=minimum))
    assert len(valid)==count
    if a.stage==2:
        interval=paired_interval([r['loss'] for r in sorted(valid,key=lambda r:r['index'])],[0]*count)
        survives=interval['ci95'][1]<.5
        write_json(stage/f'{a.arm}.json',dict(arm=a.arm,stage=2,games=count,terminal_games=count,
            loss=interval['loss_change'],loss_ci95=interval['ci95'],survives=survives,
            kill_reasons=[] if survives else ['loss upper CI >=50%'],freeze_sha256=sha(j/'freeze.json')))
    else:write_json(stage/f'{a.arm}-cases-complete.json',dict(arm=a.arm,games=count,terminal_games=count))

if __name__=='__main__':main()
