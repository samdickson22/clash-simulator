"""Bounded home-core pool; own STOP terminates only PIDs spawned by this manager."""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import resource
import socket
import subprocess
import time

p=argparse.ArgumentParser()
p.add_argument('--job',required=True);p.add_argument('--tasks',required=True)
p.add_argument('--cores',type=int,nargs='+',required=True)
p.add_argument('--freeze-sha256',required=True)
p.add_argument('--label',required=True)
a=p.parse_args();job=Path(a.job);host=socket.gethostname().split('.')[0]
caps={'127x01':48,'127x03':64,'127x04':64,'127x08':48}
assert host in caps and len(a.cores)+1<=caps[host]
assert os.getpriority(os.PRIO_PROCESS,0)>=(19 if host=='127x08' else 10)
assert os.sched_getscheduler(0)==os.SCHED_IDLE
topology=subprocess.check_output(['lscpu','-p=CPU,CORE,SOCKET'],text=True)
physical={int(s.split(',')[0]):tuple(s.split(',')[1:]) for s in topology.splitlines() if not s.startswith('#')}
assert len({physical[c] for c in a.cores})==len(a.cores)
tasks=json.loads(Path(a.tasks).read_text());pending=list(tasks);active={};done=[];failures=[]
stop=job/'REPORTING.STOP';logs=job/'reporting'/a.label;logs.mkdir(parents=True,exist_ok=True)
def request_stop(*_):stop.touch()
for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,request_stop)
start=time.monotonic();minimum=1<<62;peak=0
try:
    while pending or active:
        available=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines()
                           if s.startswith('MemAvailable:')))*1024
        minimum=min(minimum,available)
        if available<24*2**30:failures.append({'resource':'MemAvailable floor'});stop.touch()
        if stop.exists():
            for process,_,stream in active.values():process.terminate()
            for process,_,stream in active.values():
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
                stream.close()
            active.clear();break
        for core in list(active):
            process,task,stream=active[core]
            rc=process.poll()
            if rc is None:continue
            stream.close();del active[core]
            if rc:
                failures.append(dict(task=task,returncode=rc));stop.touch()
            else:done.append(task)
        for core in a.cores:
            if core in active or not pending or stop.exists():continue
            task=pending.pop(0)
            mode,arm,index=task
            stream=(logs/f'{mode}-{arm}-{index:04d}.log').open('a')
            command=['taskset','-c',str(core),'/mpac/sdicks02/repos/clasher/.venv/bin/python','-B',
                '-m','imitation.exit_r1.screen','--freeze',str(job/'execution-freeze.json'),
                '--freeze-sha256',a.freeze_sha256,'--mode',mode,'--arm',arm,
                '--offset',str(index),'--count','1','--output',str(job/'heldout' if mode=='teacher' else job/'cases'),
                '--stop',str(stop)]
            process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT)
            active[core]=(process,task,stream)
        peak=max(peak,len(active)+1)
        state=dict(host=host,completed=len(done),remaining=len(pending),active=len(active),
            failures=failures,elapsed_seconds=time.monotonic()-start,
            minimum_mem_available_bytes=minimum,peak_owned_processes=peak,
            utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        tmp=logs/'progress.partial';tmp.write_text(json.dumps(state,indent=2)+'\n');tmp.replace(logs/'progress.json')
        time.sleep(1)
finally:
    for process,_,stream in active.values():process.terminate()
    for process,_,stream in active.values():
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        stream.close()
    active.clear()
    own_usage=resource.getrusage(resource.RUSAGE_SELF)
    child_usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    (logs/'exit.json').write_text(json.dumps(dict(host=host,complete=len(done)==len(tasks),
        completed=len(done),tasks=len(tasks),failures=failures,
        elapsed_seconds=time.monotonic()-start,peak_owned_processes=peak,
        minimum_mem_available_bytes=minimum,cores=a.cores,
        manager_cpu_seconds=own_usage.ru_utime+own_usage.ru_stime,
        children_cpu_seconds=child_usage.ru_utime+child_usage.ru_stime,
        own_workers_vacated=not active),indent=2)+'\n')
if failures or len(done)!=len(tasks):raise SystemExit(1)
