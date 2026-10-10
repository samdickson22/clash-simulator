"""Owned K2 supervisor; launched only after an evidenced K-v2 release."""
import argparse,json,os,signal,socket,subprocess,time
from pathlib import Path

def utc():return subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip()
def memory():return int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024

def processes():
    rows=[]
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():continue
        try:
            stat=(d/'stat').read_text().rsplit(')',1)[1].split()
            rows.append(dict(pid=int(d.name),pgid=int(stat[2]),cmd=(d/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')))
        except (FileNotFoundError,ProcessLookupError):pass
    return rows

def release_gate(job):
    release=json.loads((job/'K-V2-RELEASE-ADMITTED.json').read_text())
    assert release['explicit_release_note'] and release['fully_vacated']
    assert not [r for r in processes() if r['pgid'] in release['pgids']]
    assert not [r for r in processes() if '/k-v2-20261010-r1/' in r['cmd'] and 'python' in r['cmd'] and not r['cmd'].startswith(('ssh','bash -c'))]
    g=Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010')
    assert (g/'STOP-03').exists()
    exited=json.loads((g/'generation/exit.json').read_text());assert exited['fully_vacated']
    assert not [r for r in processes() if r['pgid']==exited['identity']['pgid']]
    return release,exited

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--phase',choices=['smoke','reporting'],required=True);a=ap.parse_args()
    assert socket.gethostname()=='127x03'
    assert os.getpriority(os.PRIO_PROCESS,0)==10 and os.sched_getscheduler(0)==os.SCHED_OTHER
    assert os.sched_getaffinity(0)=={59} and memory()>28*2**30
    assert (a.job/'QUALIFIED').exists() and (a.job/'BELIEF-QUALIFIED').exists()
    if a.phase=='reporting':assert (a.job/'SMOKE-PASS').exists()
    release,g_exit=release_gate(a.job)
    console=subprocess.check_output(['who'],text=True)
    workers=8 if console.strip() else 11;cpus=workers*5
    pairs=8 if a.phase=='smoke' else 600
    repo=a.job/'repo';runtime=repo/'reports/explore/k2/runtime.sh';cfg=repo/'reports/explore/k2/plan.json'
    out=a.job/a.phase;out.mkdir(exist_ok=True)
    assert not (out/'receipt.json').exists(),'completed phase; do not duplicate'
    cmd=['taskset','-c',f'0-{cpus-1}','bash',str(runtime),'reports/explore/k2/run.py','--config',str(cfg),'--out',str(out),'--workers',str(workers),'--pairs',str(pairs),'--arms','K2-200','K0-200','K4-200']
    if a.phase=='smoke':cmd+=['--smoke']
    with (out/'worker.log').open('a') as log:
        child=subprocess.Popen(cmd,stdout=log,stderr=log,start_new_session=True)
        launch=dict(at_utc=utc(),supervisor_pid=os.getpid(),supervisor_pgid=os.getpgrp(),child_pid=child.pid,child_pgid=child.pid,host=socket.gethostname(),command=cmd,who=console,workers=workers,slot_physical_cpus=list(range(cpus)),arm_core_widths={'K2-200':3,'K0-200':1,'K4-200':5},nice=10,scheduler='SCHED_OTHER',G_exit=g_exit['utc'],K_v2_release=release)
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
                progress=dict(at_utc=utc(),host=socket.gethostname(),phase=a.phase,completed=len(list((out/'games').glob('*.json'))),target=pairs*3,workers=workers,slot_physical_cpus=cpus,memavailable_GiB=mem/2**30,paused=False,pid=child.pid,pgid=child.pid)
                tmp=a.job/'progress.tmp';tmp.write_text(json.dumps(progress)+'\n');tmp.replace(a.job/'progress.json');census.write(json.dumps(progress)+'\n');time.sleep(10)
        rc=child.wait();(out/'supervisor-exit.json').write_text(json.dumps(dict(at_utc=utc(),returncode=rc,min_memavailable_GiB=minimum/2**30,reason=reason))+'\n')
        if rc:raise SystemExit(rc)
    (a.job/(a.phase.upper()+'-DONE')).write_text(utc()+'\n')
if __name__=='__main__':main()
