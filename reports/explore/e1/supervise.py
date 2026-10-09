"""Own-PGID-only supervision: host caps, idle scheduling and memory pause floor."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time


def memavailable():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'): return int(line.split()[1])*1024
    raise RuntimeError('MemAvailable missing')


def processes(job):
    rows=[]
    for f in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            cmd=f.read_bytes().replace(b'\0',b' ').decode(errors='replace')
            if str(job) not in cmd or (f.parent/'comm').read_text().strip() not in ('python','python3','python3.12'):
                continue
            pid=int(f.parent.name)
            rows.append(dict(pid=pid,nice=os.getpriority(os.PRIO_PROCESS,pid),scheduler=os.sched_getscheduler(pid)))
        except (OSError,ProcessLookupError): pass
    return rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--workers',type=int,default=62)
    ap.add_argument('--phase',choices=['smoke','main','reserve'],required=True);ap.add_argument('--pairs',type=int,default=600);ap.add_argument('--offset',type=int,default=0)
    a=ap.parse_args();host=socket.gethostname();cap={'127x03':64,'127x04':32,'127x01':24}[host]
    assert a.workers+2<=cap
    assert os.sched_getscheduler(0)==os.SCHED_IDLE and os.getpriority(os.PRIO_PROCESS,0)>=10
    if memavailable()<32*2**30: raise RuntimeError('memory admission below32GiB')
    out=a.job/a.phase
    arms=['bR'] if a.phase=='reserve' else ['a0','aW','b0','bW']
    if a.phase=='smoke': arms.append('bR')
    cmd=['bash',str(a.job/'repo/reports/explore/e1/runtime.sh'),'reports/explore/e1/run.py','--config',str(a.job/'repo/reports/explore/e1/config.json'),
         '--out',str(out),'--workers',str(a.workers),'--pairs',str(a.pairs),'--offset',str(a.offset),'--arms',*arms]
    if a.phase=='smoke':cmd.append('--smoke')
    out.mkdir(parents=True,exist_ok=True)
    log=(out/'worker.log').open('a')
    start=time.time();child=subprocess.Popen(cmd,stdout=log,stderr=log,start_new_session=True)
    (out/'pids.json').write_text(json.dumps(dict(supervisor=os.getpid(),child_pgid=child.pid,host=host,command=cmd))+'\n')
    def terminate(sig,frame):
        os.killpg(child.pid,signal.SIGCONT);os.killpg(child.pid,signal.SIGTERM)
    signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate)
    paused=False;peak=0;minimum=memavailable();samples=[]
    with (out/'census.jsonl').open('a',buffering=1) as census:
        while child.poll() is None:
            memory=memavailable();rows=processes(a.job);peak=max(peak,len(rows));minimum=min(minimum,memory)
            bad=len(rows)>cap or any(r['nice']<10 or r['scheduler']!=os.SCHED_IDLE for r in rows)
            halt=(a.job/'STOP').exists()
            if bad or halt:
                os.killpg(child.pid,signal.SIGCONT);os.killpg(child.pid,signal.SIGTERM)
                samples.append(dict(time=time.time(),reason='process/scheduler cap' if bad else 'STOP file',rows=rows,memory=memory));break
            if memory<28*2**30 and not paused:
                os.killpg(child.pid,signal.SIGSTOP);paused=True;samples.append(dict(time=time.time(),pause=True,memory=memory))
            elif memory>=32*2**30 and paused:
                os.killpg(child.pid,signal.SIGCONT);paused=False;samples.append(dict(time=time.time(),pause=False,memory=memory))
            progress=dict(time=time.time(),host=host,phase=a.phase,completed=len(list((out/'games').glob('*.json'))),target=a.pairs*len(arms),
                          own_processes=len(rows),cap=cap,memavailable_GiB=memory/2**30,paused=paused)
            (a.job/'progress.json').write_text(json.dumps(progress)+'\n')
            census.write(json.dumps(dict(**progress,rows=rows))+'\n')
            time.sleep(5)
    rc=child.wait();log.close()
    (out/'supervisor-exit.json').write_text(json.dumps(dict(returncode=rc,host=host,wall_seconds=time.time()-start,
        peak_owned_processes=peak,min_memavailable_GiB=minimum/2**30,pauses_or_halts=samples))+'\n')
    raise SystemExit(rc)

if __name__=='__main__':main()
