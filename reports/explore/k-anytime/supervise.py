"""Resume only pending terminal cases, sequential stages; signal own PGID only."""
import argparse,json,os,signal,socket,subprocess,time
from pathlib import Path

def utc():return subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip()
def memory():return int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--phase',choices=['smoke','reporting'],required=True);ap.add_argument('--pairs',type=int,required=True);ap.add_argument('--offset',type=int,default=0);ap.add_argument('--cpus',type=int,required=True)
    a=ap.parse_args();host=socket.gethostname();assert host in ('127x03','127x01');assert a.cpus<={'127x03':60,'127x01':40}[host]
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getscheduler(0)==os.SCHED_IDLE
    assert os.sched_getaffinity(0)==set(range(a.cpus));assert memory()>28*2**30
    assert (a.job/'QUALIFIED').exists()
    if a.phase=='reporting': assert (a.job/'SMOKE-PASS').exists()
    repo=a.job/'repo';runtime=repo/'reports/explore/k-anytime/runtime.sh';cfg=repo/'reports/explore/k-anytime/plan.json'
    stages=[(['K0','K1','KU'],a.cpus),(['K4','K4h'],a.cpus//5)]
    for arms,workers in stages:
        out=a.job/a.phase/('single' if workers==a.cpus else 'threaded');out.mkdir(parents=True,exist_ok=True)
        if (out/'receipt.json').exists():continue
        cmd=['bash',str(runtime),'reports/explore/k-anytime/run.py','--config',str(cfg),'--out',str(out),'--workers',str(workers),'--pairs',str(a.pairs),'--offset',str(a.offset),'--arms',*arms]
        if a.phase=='smoke':cmd+=['--smoke']
        with (out/'worker.log').open('a') as log:
            child=subprocess.Popen(cmd,stdout=log,stderr=log,start_new_session=True)
            launch=dict(at_utc=utc(),supervisor_pid=os.getpid(),child_pid=child.pid,child_pgid=child.pid,host=host,command=cmd)
            (out/'launch.json').write_text(json.dumps(launch)+'\n')
            def stop(sig,frame):
                try:os.killpg(child.pid,signal.SIGCONT);os.killpg(child.pid,signal.SIGTERM)
                except ProcessLookupError:pass
            signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
            minimum=memory();paused=False
            with (out/'census.jsonl').open('a',buffering=1) as census:
                while child.poll() is None:
                    mem=memory();minimum=min(minimum,mem)
                    if (a.job/'STOP').exists():stop(None,None);break
                    if mem<24*2**30 and not paused:os.killpg(child.pid,signal.SIGSTOP);paused=True
                    elif mem>28*2**30 and paused:os.killpg(child.pid,signal.SIGCONT);paused=False
                    progress=dict(at_utc=utc(),host=host,phase=a.phase,arms=arms,completed=len(list((out/'games').glob('*.json'))),target=a.pairs*len(arms),workers=workers,physical_cpus=a.cpus,memavailable_GiB=mem/2**30,paused=paused,pid=child.pid,pgid=child.pid)
                    (a.job/'progress.json').write_text(json.dumps(progress)+'\n');census.write(json.dumps(progress)+'\n');time.sleep(10)
            rc=child.wait();(out/'supervisor-exit.json').write_text(json.dumps(dict(at_utc=utc(),returncode=rc,min_memavailable_GiB=minimum/2**30))+'\n')
            if rc:raise SystemExit(rc)
    (a.job/(a.phase.upper()+'-DONE')).write_text(utc()+'\n')
if __name__=='__main__':main()
