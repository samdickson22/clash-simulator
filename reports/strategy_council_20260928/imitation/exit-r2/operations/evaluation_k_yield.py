"""Queue home03 gates until K-v2 releases timing work, then require G drain."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from imitation.exit_r1.rows import write_json
from evaluation_g_yield import admission as g_admission

K_ROOT=Path('/mpac/sdicks02/jobs/clasher/k-v2-20261010-r1')

def k_status():
    output=subprocess.check_output(['ps','-eo','pid=,pgid=,args='],text=True)
    live=[]
    for line in output.splitlines():
        fields=line.strip().split(None,2)
        if len(fields)==3 and 'reports/explore/k-v2/run.py' in fields[2]:
            live.append(dict(pid=int(fields[0]),pgid=int(fields[1]),command=fields[2]))
    markers=sorted(str(p) for p in K_ROOT.glob('REPORTING*-DONE') if p.is_file())
    # A quiet gap before reporting does not constitute K's release.
    return dict(live_timing_processes=live,live_pgids=sorted({p['pgid'] for p in live}),
                release_markers=markers,released=bool(markers) and not live)

def home01_fit_finished(job):
    complete=job/'fits/X4/complete.json'
    if not complete.is_file() or not (job/'X4-exit.json').is_file():return False
    done=json.loads(complete.read_text())
    if done['stopped'] or done['step']!=4883:return False
    launch=json.loads((job/'X4-launch.json').read_text())
    return not any((Path('/proc')/str(launch[key])).exists() for key in ('supervisor_pid','trainer_pid'))

def admission(job,task,state):
    host=socket.gethostname().split('.')[0]
    assert host in ('127x01','127x03')
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getscheduler(0)==os.SCHED_IDLE
    if (job/'CONTROLLER.STOP').exists() or time.time()>=1791696000:return False
    if host=='127x03':
        status=k_status()
        write_json(job/'k-v2-yield-admission.json',dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),
            host=host,task=task,**status,
            rule='No03 stage1/2 evaluation before successful K-v2 reporting release and zero live timing PGIDs; ETA alone never admits.'))
        if not status['released']:return False
    elif not home01_fit_finished(job):return False
    return g_admission(job,task,state)
