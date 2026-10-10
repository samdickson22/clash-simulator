"""Owned CPU pool: continuous admission, physical cores, stops and whole-tree costs."""
import argparse,fcntl,json,os,resource,signal,subprocess,sys,time
from pathlib import Path
from exit_r3.rows import sha,write_json
from admission import allowed,context


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',required=True);ap.add_argument('--mode',choices=('regret','smoke','reporting'),required=True);ap.add_argument('--cores',type=int,nargs='+',required=True);a=ap.parse_args();j=Path(a.job)
    assert allowed(j);topology=subprocess.check_output(['lscpu','-p=CPU,CORE,SOCKET'],text=True);physical={int(l.split(',')[0]):tuple(l.split(',')[1:]) for l in topology.splitlines() if not l.startswith('#')}
    assert len({physical[c] for c in a.cores})==len(a.cores) and not set(context()['affinity'])&set(a.cores)
    assert all(0<=c<(60 if context()['host']=='127x03' else 40) for c in a.cores)
    verify=json.loads((j/'evaluation-freeze.json').read_text());pre=json.loads((j/'evaluation-prelaunch.json').read_text())
    assert pre['pushed'] and pre['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json')
    for name,want in verify['files'].items():assert sha(j/name)==want,name
    stage=j/('regret' if a.mode=='regret' else 'stage3-sdefault-smoke' if a.mode=='smoke' else 'stage3-sdefault');stage.mkdir(parents=True,exist_ok=True)
    lock=(stage/'POOL.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    arms=['C-v1']+[arm for arm in ('R3a','R3b') if json.loads((j/'offline'/f'{arm}.json').read_text())['survives']]+['K0'] if a.mode!='regret' else []
    if a.mode!='regret':assert len(arms)>2,'no scientific stage1 survivor'
    if a.mode=='reporting':assert json.loads((j/'wrapper-qualification.json').read_text())['passed']
    expected=range(64) if a.mode=='regret' else (0,1) if a.mode=='smoke' else range(600)
    pending=[];complete=[]
    for i in expected:
        marker=stage/('games' if a.mode=='regret' else 'blocks')/f'{i:04d}.json'
        if marker.exists():
            r=json.loads(marker.read_text());assert r['complete']
            if a.mode=='regret':assert sha(stage/'games'/f'{i:04d}.jsonl')==r['jsonl_sha256']
            else:
                assert r['arms']==arms and r['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json')
                for case in r['cases']:assert sha(stage/'cases'/f"sdefault-{case['arm']}-{i:04d}.json")==case['sha256']
            complete.append(i)
        else:pending.append(i)
    (stage/'logs').mkdir(exist_ok=True);active={};failures=[];stopping=False;started=time.monotonic();minimum=1<<62
    def stop(*_):
        nonlocal stopping
        stopping=True;(j/('REGRET.STOP' if a.mode=='regret' else 'REPORTING.STOP')).touch()
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
                    i=pending.pop(0);env=os.environ.copy()
                    if a.mode=='regret':
                        s=j/'scorer-source';env.update(CLASHER_ROOT=str(s),CLASHER_EVAL_RUNTIME_ROOT=str(s),CLASHER_DELAY_NATIVE_DIR=str(j/'scorer-native'),PYTHONPATH=str(s)+':'+str(s/'src')+':'+str(j/'eval-ops'))
                        command=['taskset','-c',str(core),sys.executable,'-B',str(j/'eval-ops/regret_game.py'),'--job',str(j),'--index',str(i)]
                    else:
                        command=['taskset','-c',str(core),sys.executable,'-B',str(j/'eval-ops/block.py'),'--job',str(j),'--index',str(i),'--arms',*arms]
                        if a.mode=='smoke':command.append('--smoke')
                    log=(stage/'logs'/f'{i:04d}-pool-{os.getpid()}.log').open('w');proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True);active[core]=(proc,i,log)
            write_json(stage/'progress.json',dict(mode=a.mode,arms=arms,pool_pid=os.getpid(),pool_pgid=os.getpgrp(),context=context(),utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),completed=len(complete),active={c:dict(index=i,pid=p.pid,pgid=p.pid) for c,(p,i,l) in active.items()},pending=len(pending),failures=failures,stopping=stopping))
            if stopping:
                for proc,i,log in active.values():
                    try:os.killpg(proc.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                break
            if pending or active:time.sleep(5)
    finally:
        for proc,i,log in active.values():
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            log.close()
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
        meter=dict(mode=a.mode,status='complete' if not failures and len(complete)==len(expected) else 'stopped_or_failed',host=context()['host'],arms=arms,completed=len(complete),failures=failures,parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-started,min_available_bytes=minimum,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),accounting='WHOLE pool tree once, including game/block and failed/replayed attempts. Never add nested case or game meters.')
        write_json(stage/f'pool-meter-{os.getpid()}.json',meter)
    assert meter['status']=='complete'
    write_json(stage/'POOL-DONE.json',meter)
if __name__=='__main__':main()
