"""Wait for the coordinator-authorized G filler to drain before X evaluation."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from imitation.exit_r1.rows import write_json

G_ROOT=Path("/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010")

def admission(job, task, state):
    host=socket.gethostname().split('.')[0]
    assert host in ('127x01','127x03')
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    assert os.sched_getscheduler(0)==os.SCHED_IDLE
    if (job/'CONTROLLER.STOP').exists() or time.time()>=1791696000:
        return False
    stop=G_ROOT/('STOP-03' if host=='127x03' else 'STOP-01')
    # STOP must precede the empty-process check to prevent fresh G admission.
    # The authorized G runtime already exists; never create an alternate tree.
    assert G_ROOT.is_dir(), 'G runtime absent: review admission instead of guessing'
    stop.touch(exist_ok=True)
    now=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
    state.setdefault('requested_utc',now)
    output=subprocess.check_output(['ps','-eo','pid=,pgid=,args='],text=True)
    processes=[]
    for line in output.splitlines():
        fields=line.strip().split(None,2)
        if len(fields)==3 and str(G_ROOT/'ops')+'/' in fields[2]:
            processes.append(dict(pid=int(fields[0]),pgid=int(fields[1]),command=fields[2]))
    available=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines()
                       if s.startswith('MemAvailable:')))*1024
    if processes:
        state.pop('empty_since',None)
        admitted=False
    else:
        state.setdefault('empty_since',time.monotonic())
        admitted=time.monotonic()-state['empty_since']>=1 and available>=24*2**30
    write_json(job/'g-yield-admission.json',dict(utc=now,host=host,task=task,
        stop_file=str(stop),requested_utc=state['requested_utc'],g_processes=processes,
        admitted=admitted,mem_available_bytes=available,load1=os.getloadavg()[0],
        rule='STOP before scan; all G ops processes must exit; two empty samples and home24GiB floor'))
    return admitted
