"""One bounded home pool consumes immutable stage queues until explicit drain."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import socket
import subprocess
import time

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--job',required=True)
p.add_argument('--cores',type=int,nargs='+',required=True);p.add_argument('--host',required=True);p.add_argument('--stop')
a=p.parse_args();job=Path(a.job);host=socket.gethostname().split('.')[0]
assert host=='127x'+a.host and host in ('127x03','127x04','127x01','127x08')
assert len(a.cores)<={'03':56,'04':60,'01':44,'08':48}[a.host]
assert os.getpriority(os.PRIO_PROCESS,0)>=(19 if a.host=='08' else 10) and os.sched_getscheduler(0)==os.SCHED_IDLE
topology=subprocess.check_output(['lscpu','-p=CPU,CORE,SOCKET'],text=True)
physical={int(s.split(',')[0]):tuple(s.split(',')[1:]) for s in topology.splitlines() if not s.startswith('#')}
assert len({physical[c] for c in a.cores})==len(a.cores)
inbox=job/'stage-queues'/a.host;inbox.mkdir(parents=True,exist_ok=True)
logs=job/'reporting/staged-r1';logs.mkdir(parents=True,exist_ok=True)
stop=Path(a.stop) if a.stop else job/'REPORTING.STOP';drain=inbox/'DRAIN'
pending=[];active={};done=[];failures=[];queues={};identities=set()
assert a.host!='08' or (set(a.cores)==set(range(2,50)) and a.stop)
start=time.monotonic();minimum=1<<62;peak=0
def request_stop(*_):stop.touch()
for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,request_stop)
try:
    while True:
        for path in sorted(inbox.glob('*.json')):
            if path.name in queues:continue
            q=json.loads(path.read_text());assert q['host']==a.host
            assert sha(q['freeze'])==q['freeze_sha256']
            queues[path.name]=sha(path)
            for task in q['tasks']:
                key=tuple(task);assert key not in identities,key;identities.add(key)
                pending.append(dict(task=task,stage=q['stage'],freeze=q['freeze'],freeze_sha256=q['freeze_sha256']))
        available=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024
        minimum=min(minimum,available)
        if available<24*2**30:failures.append({'resource':'MemAvailable floor'});stop.touch()
        if stop.exists():break
        for core in list(active):
            process,item,stream=active[core];rc=process.poll()
            if rc is None:continue
            stream.close();del active[core]
            if rc:failures.append(dict(task=item,returncode=rc));stop.touch()
            else:done.append(item)
        if stop.exists():continue
        for core in a.cores:
            if core in active or not pending:continue
            item=pending.pop(0);mode,arm,index=item['task']
            stream=(logs/f'{mode}-{arm}-{index:04d}.log').open('a')
            output=job/'heldout' if mode=='teacher' else job/'stage-cases'/item['stage']
            cmd=['taskset','-c',str(core),'/mpac/sdicks02/repos/clasher/.venv/bin/python','-B',
                '-m','imitation.exit_r1.screen','--freeze',item['freeze'],'--freeze-sha256',item['freeze_sha256'],
                '--mode',mode,'--arm',arm,'--offset',str(index),'--count','1','--output',str(output),'--stop',str(stop)]
            process=subprocess.Popen(cmd,stdout=stream,stderr=subprocess.STDOUT);active[core]=(process,item,stream)
        peak=max(peak,len(active)+1)
        state=dict(host=host,completed=len(done),remaining=len(pending),active=len(active),
            queue_sha256=queues,failures=failures,elapsed_seconds=time.monotonic()-start,
            minimum_mem_available_bytes=minimum,peak_owned_processes=peak,
            utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        tmp=logs/'progress.partial';tmp.write_text(json.dumps(state,indent=2)+'\n');tmp.replace(logs/'progress.json')
        if drain.exists() and not pending and not active:break
        time.sleep(1)
finally:
    for process,_,_ in active.values():process.terminate()
    for process,_,stream in active.values():
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        stream.close()
    active.clear();own=resource.getrusage(resource.RUSAGE_SELF);children=resource.getrusage(resource.RUSAGE_CHILDREN)
    (logs/'exit.json').write_text(json.dumps(dict(host=host,complete=drain.exists() and len(done)==len(identities) and not failures,
        completed=len(done),tasks=len(identities),failures=failures,queue_sha256=queues,
        elapsed_seconds=time.monotonic()-start,peak_owned_processes=peak,minimum_mem_available_bytes=minimum,
        cores=a.cores,manager_cpu_seconds=own.ru_utime+own.ru_stime,
        children_cpu_seconds=children.ru_utime+children.ru_stime,own_workers_vacated=True,stop_file=str(stop),stop_requested=stop.exists()),indent=2)+'\n')
if failures or len(done)!=len(identities) or not drain.exists():raise SystemExit(1)
