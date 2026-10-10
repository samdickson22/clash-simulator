"""Exclusive01 supervisor with exact runtime guard and whole-tree cost meters."""
import argparse,hashlib,json,os,resource,signal,socket,subprocess,time
from pathlib import Path
from host_audit import processes,foreign_compute,release_gate,utc,memory

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def runtime_guard(job):
    pin=json.loads((job/'runtime-pin.json').read_text())
    for name,h in pin['files'].items():assert sha(job/'repo'/name)==h,name
    assert sha(job/'native/clasher_core.abi3.so')==pin['native_sha256']
    assert sha(job/'inputs/R3a.pt')==pin['checkpoint_sha256']
    assert sha(job/'inputs/main02.pt')==pin['policy_sha256']
    assert sha(job/'inputs/R3a-calibration.json')==pin['calibration_sha256']
    return pin

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--phase',choices=['smoke','reporting'],required=True);a=ap.parse_args();job=a.job
    assert socket.gethostname()=='127x01' and os.sched_getaffinity(0)=={39}
    assert os.getpriority(os.PRIO_PROCESS,0)==10 and os.sched_getscheduler(0)==os.SCHED_OTHER
    release=release_gate(job);assert not foreign_compute(job,processes())
    assert (job/'QUALIFIED').exists() and (job/'BELIEF-QUALIFIED').exists() and (job/'TESTS-PASS').exists()
    if a.phase=='reporting':assert (job/'SMOKE-PASS').exists()
    pin=runtime_guard(job)
    console=subprocess.check_output(['who'],text=True);workers=10 if console.strip() else 13
    pairs=8 if a.phase=='smoke' else 600
    out=job/a.phase;out.mkdir(exist_ok=True)
    assert not (out/'receipt.json').exists(),'no duplicate phase'
    cmd=['taskset','-c',f'0-{workers*3-1}','bash',str(job/'repo/reports/explore/s1/runtime.sh'),'reports/explore/s1/run.py','--config',str(job/'repo/reports/explore/s1/plan.json'),'--out',str(out),'--workers',str(workers),'--pairs',str(pairs)]
    if a.phase=='smoke':cmd.append('--smoke')
    t=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
    reason=None;minimum=memory()
    with (out/'worker.log').open('a') as log:
        child=subprocess.Popen(cmd,stdout=log,stderr=log,start_new_session=True)
        launch=dict(utc=utc(),supervisor_pid=os.getpid(),supervisor_pgid=os.getpgrp(),child_pid=child.pid,child_pgid=child.pid,command=cmd,who=console,workers=workers,slot_physical_cpus=list(range(workers*3)),freeze_commit=pin['freeze_commit'],plan_sha256=pin['plan_sha256'],runtime_pin_sha256=sha(job/'runtime-pin.json'),release=release)
        (out/'launch.json').write_text(json.dumps(launch,indent=2)+'\n')
        def stop(sig,frame):
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        while child.poll() is None:
            mem=memory();minimum=min(minimum,mem)
            foreign=foreign_compute(job,processes())
            if (job/'STOP').exists() or mem<24*2**30 or foreign:
                reason='owned_STOP' if (job/'STOP').exists() else 'memory_floor' if mem<24*2**30 else 'foreign_compute'
                (out/'stop-reason.json').write_text(json.dumps(dict(utc=utc(),reason=reason,foreign=foreign))+'\n');stop(None,None);break
            games=list((out/'games').glob('*.json'))
            progress=dict(utc=utc(),phase=a.phase,completed_games=len(games),target_games=pairs*5,complete_blocks=len(list((out/'blocks').glob('*.json'))),memavailable_GiB=mem/2**30,child_pid=child.pid,child_pgid=child.pid,workers=workers)
            temp=job/'progress.tmp';temp.write_text(json.dumps(progress)+'\n');temp.replace(job/'progress.json')
            with (out/'census.jsonl').open('a') as census:census.write(json.dumps(progress)+'\n')
            time.sleep(10)
        rc=child.wait()
    runtime_guard(job)
    after=resource.getrusage(resource.RUSAGE_CHILDREN);own=resource.getrusage(resource.RUSAGE_SELF)
    result=dict(utc=utc(),returncode=rc,reason=reason,min_memavailable_GiB=minimum/2**30,wall_seconds=time.monotonic()-t,children_cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,parent_cpu_seconds=own.ru_utime+own.ru_stime,whole_tree_cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime+own.ru_utime+own.ru_stime,accounting='whole phase tree once; nested game CPU not added')
    (out/'supervisor-exit.json').write_text(json.dumps(result,indent=2)+'\n')
    if rc or reason:raise SystemExit(rc or 1)
if __name__=='__main__':main()
