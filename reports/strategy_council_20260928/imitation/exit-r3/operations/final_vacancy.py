"""Metadata-only04 reducer observation and independent final process drain."""
import argparse,hashlib,json,os,resource,subprocess,time
from pathlib import Path

J=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def census():
    result=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            fields=(p/'stat').read_text().rsplit(')',1)[1].split()
            result.append(dict(pid=int(p.name),pgid=int(fields[2]),start_ticks=int(fields[19]),command=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')))
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    return result
def save(name,r):
    p=J/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(r,indent=2)+'\n');t.replace(p)
def main():
    p=argparse.ArgumentParser();p.add_argument('--observe-reducer',action='store_true');a=p.parse_args()
    from guard_regret04 import allowed,full_pressure
    assert allowed(J,manager=True) and os.sched_getaffinity(0)=={19}
    started=time.monotonic();own=dict(pid=os.getpid(),pgid=os.getpgrp(),nice=os.getpriority(os.PRIO_PROCESS,0),affinity=sorted(os.sched_getaffinity(0)),scheduler=os.sched_getscheduler(0))
    if a.observe_reducer:
        assert not (J/'REGRET04-REDUCTION-IDENTITY.json').exists(),'observation already recorded; review before retry'
        print('observer-ready',flush=True);seen={}
        while time.monotonic()-started<30:
            assert allowed(J,manager=True)
            for v in census():
                if v['command'].startswith('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1/venv/bin/python -B ') and str(J/'eval-ops/reduce.py') in v['command'] and '--mode regret' in v['command']:
                    v.update(nice=os.getpriority(os.PRIO_PROCESS,v['pid']),affinity=sorted(os.sched_getaffinity(v['pid'])),scheduler=os.sched_getscheduler(v['pid']))
                    assert v['nice']==19 and v['affinity']==[19] and v['scheduler']==os.SCHED_OTHER
                    seen[v['pid']]=v
            if seen and all(not (Path('/proc')/str(pid)).exists() for pid in seen):break
            time.sleep(.05)
        assert len(seen)==1,'exactly one pinned reducer must have been observed'
        r=dict(host='127x04',observer=own,reducers=list(seen.values()),reducer_sha256=digest(J/'eval-ops/reduce.py'),evaluation_freeze_sha256=digest(J/'evaluation-freeze.json'))
        name='REGRET04-REDUCTION-IDENTITY.json'
    else:
        v=load(J/'REGRET04-VACATED.json');journal=load(J/'REGRET04-PGIDS.json');observation=load(J/'REGRET04-REDUCTION-IDENTITY.json')
        assert v['children_reaped'] and v['status']=='complete' and v['completed']==64
        assert v['recorded_identities_sha256']==digest(J/'REGRET04-PGIDS.json')
        assert sorted(set(v['pgids']))==sorted(set(i['pgid'] for i in journal))
        assert load(J/'regret/POOL-DONE.json')['status']=='complete'
        assert all(r['stage1_complete'] for r in load(J/'stage1-results.json').values())
        pgids=set(v['pgids']);pgids.update(r['pgid'] for r in observation['reducers']);pgids.add(observation['observer']['pgid']);pgids.update((865011,1023059,1040730,1126275))
        processes=census();remaining=[p for p in processes if p['pgid'] in pgids]
        runtime=[p for p in processes if str(J) in p['command'] and not p['command'].startswith(('ssh ','sshd:','rsync ')) and p['pid']!=os.getpid()]
        assert not remaining and not runtime,(remaining,runtime)
        r=dict(host='127x04',passed=True,vacated=True,all_absent=True,recorded_pgids=sorted(pgids),remaining=remaining,active_owned_runtime=runtime,auditor=own,pool_vacancy_sha256=digest(J/'REGRET04-VACATED.json'),journal_sha256=digest(J/'REGRET04-PGIDS.json'),reduction_identity_sha256=digest(J/'REGRET04-REDUCTION-IDENTITY.json'),authority_sha256=digest(J/'REGRET04-AUTHORITY.json'),admission_sha256=digest(J/'REGRET04-ADMITTED.json'),psi_full_avg10=full_pressure())
        name='REGRET04-INDEPENDENT-VACATED.json'
    utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip();u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
    r.update(cpu_seconds=u.ru_utime+u.ru_stime+v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-started,utc=utc,audit_source_sha256=digest(Path(__file__)))
    save(name,r);print(json.dumps(r),flush=True)
if __name__=='__main__':main()
