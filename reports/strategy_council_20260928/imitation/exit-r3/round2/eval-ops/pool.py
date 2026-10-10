"""Admitted home01 paired pool, stops and whole-tree costs; no auto retries."""
import argparse,fcntl,json,os,resource,signal,subprocess,sys,time
from pathlib import Path
from admission import allowed,context,frozen,sha
from protocol import BASES,stage,arm_list
from journal import record
from imitation.exit_r1.rows import write_json
def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--lane',choices=tuple(BASES),required=True);p.add_argument('--smoke',action='store_true');p.add_argument('--cores',type=int,nargs='+',required=True);a=p.parse_args();j=Path(a.job)
    assert allowed(j) and os.sched_getaffinity(0)=={39};frozen(j)
    assert len(a.cores)==len(set(a.cores)) and set(a.cores)<=set(range(39))
    topology={int(l.split(',')[0]):tuple(l.split(',')[1:]) for l in subprocess.check_output(['lscpu','-p=CPU,CORE,SOCKET'],text=True).splitlines() if not l.startswith('#')}
    assert len({topology[c] for c in a.cores})==len(a.cores)
    arms=arm_list(a.lane,json.loads((j/'stage1-results.json').read_text()) if a.lane=='stage2' else None);assert len(arms)>1
    folder=j/stage(a.lane,a.smoke);folder.mkdir(exist_ok=True);lock=(folder/'POOL.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if not a.smoke:
        q=json.loads((j/('qualification-'+a.lane+'.json')).read_text());assert q['passed'] and q['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json')
    expected=list(range(2 if a.smoke else 600));complete=[];pending=[]
    for i in expected:
        path=folder/'blocks'/f'{i:04d}.json'
        if path.exists():
            v=json.loads(path.read_text());assert v['complete'] and v['arms']==arms and v['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json')
            for item in v['cases']:assert sha(folder/'cases'/f"fallback-{item['arm']}-{i:04d}.json")==item['sha256']
            complete.append(i)
        else:pending.append(i)
    record(j,'pool',lane=a.lane,smoke=a.smoke);(folder/'logs').mkdir(exist_ok=True);active={};failures=[];stopping=False;start=time.monotonic();minimum=1<<62
    def stop(*_):
        nonlocal stopping
        stopping=True;(j/'REPORTING.STOP').touch()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        while pending or active:
            if not allowed(j):stopping=True
            available=int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))*1024;minimum=min(minimum,available)
            for core,(proc,i,log) in list(active.items()):
                if proc.poll() is not None:
                    code=proc.wait();log.close();del active[core]
                    if code:failures.append(dict(index=i,exit_code=code));stopping=True
                    else:complete.append(i)
            if not stopping:
                for core in a.cores:
                    if core in active or not pending:continue
                    i=pending.pop(0);cmd=['taskset','-c',str(core),sys.executable,'-B',str(j/'eval-ops/block.py'),'--job',str(j),'--lane',a.lane,'--index',str(i)]
                    if a.smoke:cmd+=['--smoke']
                    log=(folder/'logs'/f'{i:04d}-pool-{os.getpid()}.log').open('w');proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);active[core]=(proc,i,log)
            write_json(folder/'progress.json',dict(lane=a.lane,smoke=a.smoke,arms=arms,pool_pid=os.getpid(),pool_pgid=os.getpgrp(),context=context(),completed=len(complete),pending=len(pending),active={c:dict(index=i,pid=p.pid,pgid=p.pid) for c,(p,i,l) in active.items()},failures=failures,stopping=stopping))
            if stopping:break
            if pending or active:time.sleep(3)
    finally:
        for proc,i,log in active.values():
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            log.close()
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
        meter=dict(lane=a.lane,smoke=a.smoke,arms=arms,pid=os.getpid(),pgid=os.getpgrp(),status='complete' if not failures and len(complete)==len(expected) else 'stopped_or_failed',completed=len(complete),failures=failures,parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-start,min_available_bytes=minimum,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),accounting='Whole pool tree once including interpreter startup, source verification and failed/replayed cases; nested case meters never added')
        write_json(folder/f'pool-meter-{os.getpid()}.json',meter)
    assert meter['status']=='complete';write_json(folder/'POOL-DONE.json',meter)
if __name__=='__main__':main()
