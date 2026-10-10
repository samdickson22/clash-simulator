"""Fresh independent X-release/drain audit; JSON/proc/lock metadata only."""
import argparse,fcntl,hashlib,json,os,socket,subprocess,time
from pathlib import Path
J=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2')
B=Path('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1')
G=Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010')
RELEASE_SHA='fc8fbf9a1473213b176da69795420c7af7d40dbf76f81e0b365ce36cd0e9f215'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert socket.gethostname().split('.')[0]=='127x01'
    assert os.getpriority(os.PRIO_PROCESS,0)==10 and os.sched_getscheduler(0)==os.SCHED_OTHER and os.sched_getaffinity(0)=={39}
    p=B/'POSTKILL-CPU-RELEASE.json';r=json.loads(p.read_text());assert digest(p)==RELEASE_SHA
    assert r['released'] and r['reporting_complete'] and r['host']=='127x01' and r['paired_blocks']==600 and r['terminal_games']==3000
    pgids={r['pool_pid'],r['reducer_pid'],*r['artifact_mirror_pids']}
    for folder in ('postkill-sdefault/blocks','postkill-sdefault-smoke/blocks'):
        for p in (B/folder).glob('*.json'):
            v=json.loads(p.read_text());pgids.add(v['parent_pid'])
    assert len(pgids)>=604
    observed=[];conflicts=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            pid=int(p.name);group=os.getpgid(pid);cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            if group in pgids:observed.append(dict(pid=pid,pgid=group))
            if cmd.startswith(('ssh ','sshd:','rsync ')):continue
            if any(s in cmd for s in ('/k2-20261010','/k-v2-20261010-r1/',str(G/'ops')+'/')) or ('exit-r2' in cmd and any(s in cmd for s in ('/game_pool','/game_worker','/postkill','/descriptive'))):conflicts.append(dict(pid=pid,pgid=group,command=cmd[:600]))
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    assert not observed and not conflicts,(observed,conflicts)
    locks={}
    for name in ('POOL.lock','REDUCE.lock'):
        p=B/'postkill-sdefault'/name
        assert p.exists(),str(p)
        with p.open('rb') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);locks[name]='free';fcntl.flock(f,fcntl.LOCK_UN)
    assert (G/'STOP').exists() and (G/'STOP-01').exists()
    available=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024
    assert available>=24*2**30 and time.time()<1791695700
    J.mkdir(parents=True,exist_ok=True)
    evidence=dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),host='127x01',explicit_notification='X user release06:47:05Z',release_sha256=RELEASE_SHA,release=r,pgids=sorted(pgids),active_released_pgids=observed,conflicts=conflicts,locks=locks,G_stops_retained=True,mem_available_bytes=available,passed=True)
    p=J/'CPU-RELEASE-EVIDENCE.json';assert not p.exists(),'manual review and version required for re-admission';p.write_text(json.dumps(evidence,indent=2)+'\n')
    admitted=dict(explicit_release=True,host='127x01',physical_cores=list(range(40)),nice=10,scheduler='SCHED_OTHER',manager_core=39,vacated_pgids=sorted(pgids),release_evidence_sha256=digest(p),release_evidence_path=p.name,utc=evidence['utc'])
    (J/'CPU-RELEASE-ADMITTED.json').write_text(json.dumps(admitted,indent=2)+'\n');print(json.dumps(admitted))
if __name__=='__main__':main()
