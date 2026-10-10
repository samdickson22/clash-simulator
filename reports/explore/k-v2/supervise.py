"""Owned normal-priority supervisor; no process outside recorded children is signaled."""
import argparse,json,os,signal,socket,subprocess,time
from pathlib import Path

def utc():return subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip()
def memory():return int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--phase',choices=['smoke','reporting','smoke-r2','smoke-r3','reporting-r2'],required=True);a=ap.parse_args()
    assert socket.gethostname()=='127x03'
    assert os.getpriority(os.PRIO_PROCESS,0)==10 and os.sched_getscheduler(0)==os.SCHED_OTHER
    assert os.sched_getaffinity(0)=={45} and memory()>28*2**30
    assert (a.job/'QUALIFIED').exists()
    kind=a.phase.split('-')[0]
    if a.phase.endswith(('-r2','-r3')):
        assert (a.job/'BELIEF-QUALIFIED').exists()
    if kind=='reporting':
        assert (a.job/('SMOKE-R3-PASS' if a.phase.endswith('-r2') else 'SMOKE-PASS')).exists()
    console=subprocess.check_output(['who'],text=True)
    workers=6 if console.strip() else 9;cpus=workers*5
    g=Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010')
    assert (g/'STOP-03').exists()
    exited=json.loads((g/'generation/exit.json').read_text());assert exited['fully_vacated']
    gpgid=exited['identity']['pgid']
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():continue
        try:
            # /proc stat comm may contain spaces; parse after last ')'.
            fields=(d/'stat').read_text().rsplit(')',1)[1].split()
            assert int(fields[2])!=gpgid,('G process still alive',d.name)
        except FileNotFoundError:pass
    pairs=8 if kind=='smoke' else 600
    repo=a.job/'repo';runtime=repo/'reports/explore/k-v2/runtime.sh';cfg=repo/'reports/explore/k-v2/plan.json'
    out=a.job/a.phase;out.mkdir(exist_ok=True)
    assert not (out/'receipt.json').exists(),'completed phase; do not duplicate'
    cmd=['taskset','-c',f'0-{cpus-1}','bash',str(runtime),'reports/explore/k-v2/run.py','--config',str(cfg),'--out',str(out),'--workers',str(workers),'--pairs',str(pairs),'--arms','V200','V160','V120','K0-200']
    if kind=='smoke':cmd+=['--smoke']
    with (out/'worker.log').open('a') as log:
        child=subprocess.Popen(cmd,stdout=log,stderr=log,start_new_session=True)
        launch=dict(at_utc=utc(),supervisor_pid=os.getpid(),supervisor_pgid=os.getpgrp(),child_pid=child.pid,child_pgid=child.pid,host=socket.gethostname(),command=cmd,who=console,workers=workers,physical_cpus=list(range(cpus)),nice=10,scheduler='SCHED_OTHER',G_exit=exited['utc'])
        (out/'launch.json').write_text(json.dumps(launch,indent=2)+'\n')
        def stop(sig,frame):
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        minimum=memory();reason=None
        with (out/'census.jsonl').open('a',buffering=1) as census:
            while child.poll() is None:
                mem=memory();minimum=min(minimum,mem)
                if (a.job/'STOP').exists() or mem<24*2**30:
                    reason='owned_STOP' if (a.job/'STOP').exists() else 'memory_floor'
                    stop(None,None);break
                progress=dict(at_utc=utc(),host=socket.gethostname(),phase=a.phase,completed=len(list((out/'games').glob('*.json'))),target=pairs*4,workers=workers,physical_cpus=cpus,memavailable_GiB=mem/2**30,paused=False,pid=child.pid,pgid=child.pid)
                tmp=a.job/'progress.tmp';tmp.write_text(json.dumps(progress)+'\n');tmp.replace(a.job/'progress.json');census.write(json.dumps(progress)+'\n');time.sleep(10)
        rc=child.wait();(out/'supervisor-exit.json').write_text(json.dumps(dict(at_utc=utc(),returncode=rc,min_memavailable_GiB=minimum/2**30,reason=reason))+'\n')
        if rc:raise SystemExit(rc)
    (a.job/(a.phase.upper()+'-DONE')).write_text(utc()+'\n')
if __name__=='__main__':main()
