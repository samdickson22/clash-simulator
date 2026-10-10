"""64 common command-exact frozen-W replay games, on admitted03 only."""
import argparse,fcntl,json,os,resource,signal,subprocess,sys,time
from pathlib import Path
from regret_admission import allowed,frozen
from admission import sha,context
from journal import record
from imitation.exit_r1.rows import write_json
def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);a=p.parse_args();j=Path(a.job);assert allowed(j) and os.sched_getaffinity(0)=={59};frozen(j)
    assert json.loads((j/'REGRET-PROPOSALS-STAGING.json').read_text())['passed']
    folder=j/'regret';folder.mkdir(exist_ok=True);lock=(folder/'POOL.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    complete=[];pending=[]
    for i in range(64):
        p=folder/'games'/f'{i:04d}.json'
        if p.exists():
            v=json.loads(p.read_text());assert v['complete'] and v['command_exact'] and v['jsonl_sha256']==sha(p.with_suffix('.jsonl')) and v['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json');complete.append(i)
        else:pending.append(i)
    record(j,'regret_pool');(folder/'logs').mkdir(exist_ok=True);active={};failures=[];stopping=False;t=time.monotonic();minimum=1<<62
    def stop(*_):
        nonlocal stopping
        stopping=True;(j/'REGRET.STOP').touch()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        while pending or active:
            if not allowed(j):stopping=True
            available=int(next(v.split()[1] for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith('MemAvailable:')))*1024;minimum=min(minimum,available)
            for core,(proc,i,log) in list(active.items()):
                if proc.poll() is not None:
                    code=proc.wait();log.close();del active[core]
                    if code:failures.append(dict(index=i,exit_code=code));stopping=True
                    else:complete.append(i)
            if not stopping:
                for core in range(8):
                    if core in active or not pending:continue
                    i=pending.pop(0);log=(folder/'logs'/f'{i:04d}-pool-{os.getpid()}.log').open('w');cmd=['taskset','-c',str(core),sys.executable,'-B',str(j/'eval-ops/regret_game.py'),'--job',str(j),'--index',str(i)];proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);active[core]=(proc,i,log)
            write_json(folder/'progress.json',dict(pool_pid=os.getpid(),pool_pgid=os.getpgrp(),context=context(),completed=len(complete),pending=len(pending),active={c:dict(index=i,pid=p.pid,pgid=p.pid) for c,(p,i,l) in active.items()},failures=failures,stopping=stopping))
            if stopping:break
            if pending or active:time.sleep(3)
    finally:
        for proc,i,log in active.values():
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            log.close()
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN);meter=dict(status='complete' if len(complete)==64 and not failures else 'stopped_or_failed',pid=os.getpid(),pgid=os.getpgrp(),completed=len(complete),failures=failures,parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-t,min_available_bytes=minimum,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),accounting='Whole replay pool tree once; nested game/row diagnostics never added');write_json(folder/f'pool-meter-{os.getpid()}.json',meter)
    assert meter['status']=='complete';write_json(folder/'POOL-DONE.json',meter)
if __name__=='__main__':main()
