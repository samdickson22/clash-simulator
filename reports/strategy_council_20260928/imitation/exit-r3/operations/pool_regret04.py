"""Three scoring children plus manager; stop/vacate on PSI or A19 authority change."""
import argparse,fcntl,hashlib,json,os,resource,signal,subprocess,sys,time
from pathlib import Path
from exit_r3.rows import sha,write_json
from guard_regret04 import allowed,full_pressure

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);a=p.parse_args();j=Path(a.job)
    assert allowed(j,manager=True) and os.sched_getaffinity(0)=={19}
    freeze=json.loads((j/'evaluation-freeze.json').read_text());pre=json.loads((j/'evaluation-prelaunch.json').read_text())
    assert pre['pushed'] and pre['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json')
    for name,want in freeze['files'].items():assert sha(j/name)==want,name
    assert json.loads((j/'REGRET04-STAGING.json').read_text())['passed']
    stage=j/'regret';stage.mkdir(exist_ok=True);(stage/'logs').mkdir(exist_ok=True)
    lock=(stage/'POOL.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    admission=json.loads((j/'REGRET04-ADMITTED.json').read_text());progress_paths=admission['a19_progress_sha256']
    authority=json.loads((j/'REGRET04-AUTHORITY.json').read_text())
    assert sha(j/'REGRET04-AUTHORITY.json')==freeze['regret04_authority_sha256']
    assert authority['progress_sha_changes_are_bookkeeping'] and authority['absolute_vacate_utc']=='2026-10-10T07:30:00Z'
    complete=[];pending=[]
    for i in range(64):
        path=stage/'games'/f'{i:04d}.json'
        if path.exists():
            r=json.loads(path.read_text());assert r['complete'] and sha(path.with_suffix('.jsonl'))==r['jsonl_sha256'];complete.append(i)
        else:pending.append(i)
    active={};failures=[];reason=None;started=time.monotonic();peak=0.
    journal=j/'REGRET04-PGIDS.json'
    identities=json.loads(journal.read_text()) if journal.exists() else []
    identities.append(dict(role='pool',pid=os.getpid(),pgid=os.getpgrp(),core=19,nice=19,started_epoch=time.time()))
    write_json(journal,identities)
    def stop(cause):
        nonlocal reason
        if reason is None:reason=cause;(j/'REGRET04.STOP').write_text(cause+'\n')
    signal.signal(signal.SIGTERM,lambda *_:stop('SIGTERM; vacate'))
    signal.signal(signal.SIGINT,lambda *_:stop('SIGINT; vacate'))
    try:
        while pending or active:
            peak=max(peak,full_pressure())
            if not allowed(j,manager=True):stop('live04 admission/PSI/deadline/A19/stop guard')
            if reason is None:
                # Only one transient helper from this manager, at most three
                # worker date helpers:1manager+3workers+3date+1ssh=8processes.
                command='sha256sum '+' '.join(progress_paths)
                try:
                    check=subprocess.run(['ssh','-o','ConnectTimeout=2','127x05',command],capture_output=True,text=True,timeout=3,check=True)
                    actual={line.split()[1]:line.split()[0] for line in check.stdout.splitlines()}
                    assert set(actual)==set(progress_paths),'incomplete A19 progress availability check'
                    # Coordinator clarified that review/approval bookkeeping
                    # changes these files without admitting a launch. Preserve
                    # the observed hashes; actual launch/STOP/07:30 guards stay.
                    progress_paths=actual
                except Exception:stop('A19 progress check unavailable; vacate')
            write_json(j/'REGRET04-HEARTBEAT.json',dict(allowed=reason is None,checked_epoch=time.time(),manager_pid=os.getpid(),manager_pgid=os.getpgrp(),a19_observed_progress_sha256=progress_paths))
            for core,(child,i,log) in list(active.items()):
                if child.poll() is not None:
                    code=child.wait();log.close();del active[core]
                    if code:failures.append(dict(index=i,exit_code=code));stop('scoring child failure')
                    else:complete.append(i)
            if reason is None:
                for core in (12,13,14):
                    if core in active or not pending:continue
                    i=pending.pop(0);log=(stage/'logs'/f'{i:04d}-pool-{os.getpid()}.log').open('w')
                    env=os.environ.copy();s=j/'scorer-source';env.update(R3_REGRET04='1',CLASHER_ROOT=str(s),CLASHER_EVAL_RUNTIME_ROOT=str(s),CLASHER_DELAY_NATIVE_DIR=str(j/'scorer-native'),PYTHONPATH=str(s)+':'+str(s/'src')+':'+str(j/'eval-ops'))
                    command=['taskset','-c',str(core),sys.executable,'-B',str(j/'eval-ops/regret_game.py'),'--job',str(j),'--index',str(i)]
                    child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True);active[core]=(child,i,log)
                    identities.append(dict(role='scoring_game',index=i,pid=child.pid,pgid=child.pid,core=core,nice=19,started_epoch=time.time()))
                    write_json(journal,identities)
            write_json(stage/'progress.json',dict(mode='regret04',pool_pid=os.getpid(),pool_pgid=os.getpgrp(),host='127x04',nice=19,cores=[12,13,14],manager_core=19,completed=len(complete),pending=len(pending),active={c:dict(index=i,pid=p.pid,pgid=p.pid) for c,(p,i,l) in active.items()},failures=failures,reason=reason,checked_epoch=time.time()))
            if reason is not None:
                for child,i,log in active.values():
                    try:os.killpg(child.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                break
            if pending or active:time.sleep(1)
    finally:
        for child,i,log in active.values():
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            log.close()
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
        meter=dict(mode='regret04',status='complete' if reason is None and len(complete)==64 else 'stopped_or_failed',host='127x04',pool_pid=os.getpid(),pool_pgid=os.getpgrp(),completed=len(complete),reason=reason,failures=failures,parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-started,peak_full_avg10=peak,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),accounting='Whole pool tree once; all scoring/helper/failed/replayed CPU included. Nested worker meters never added.')
        write_json(stage/f'pool-meter-{os.getpid()}.json',meter)
        write_json(j/'REGRET04-VACATED.json',dict(**meter,children_reaped=True,recorded_identities_sha256=sha(journal),pgids=[v['pgid'] for v in identities]))
    assert meter['status']=='complete'
    write_json(stage/'POOL-DONE.json',meter)
if __name__=='__main__':main()
