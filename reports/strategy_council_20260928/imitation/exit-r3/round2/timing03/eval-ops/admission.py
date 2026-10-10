"""Timing03 only after coordinator G release and independent full drain.

This is distinct from the shared regret grant. Missing evidence fails closed;
no signals, retries, STOP clearing, or admission by projected finish time.
"""
import hashlib,json,os,socket,time
from pathlib import Path

G=Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def context():
    return dict(host=socket.gethostname().split('.')[0],affinity=sorted(os.sched_getaffinity(0)),nice=os.getpriority(os.PRIO_PROCESS,0),scheduler=os.sched_getscheduler(0))


_checked=0.
_conflicts=[]


def allowed(job):
    global _checked,_conflicts
    j=Path(job);c=context()
    if c['host']!='127x03' or c['nice']!=10 or c['scheduler']!=os.SCHED_OTHER or not set(c['affinity'])<=set(range(56)):return False
    if time.time()>=1791695700 or any((j/s).exists() for s in ('REPORTING.STOP','EVAL.STOP')) or (j.parent/'EVAL.STOP').exists():return False
    if not (G/'STOP-03').exists():return False
    p=j/'CPU-RELEASE-ADMITTED.json'
    if not p.exists():return False
    r=json.loads(p.read_text());e=j/r['release_evidence_path']
    if not r.get('explicit_coordinator_G_release') or not r.get('independent_full_drain') or r.get('host')!='127x03' or r.get('physical_cores')!=list(range(56)):return False
    if sha(e)!=r['release_evidence_sha256'] or sha(j/'TIMING03-AUTHORITY.json')!=r['authority_sha256']:return False
    if sha(j.parent/'stage1-results.json')!=r['stage1_results_sha256']:return False
    s=json.loads((j.parent/'stage1-results.json').read_text())
    if set(s)!={'R3c','R3d','R3e'} or not all(v['stage1_complete'] for v in s.values()) or not any(v['survives'] for v in s.values()):return False
    if time.monotonic()-_checked>=5:
        conflicts=[]
        for p in Path('/proc').iterdir():
            if not p.name.isdigit():continue
            try:
                pid=int(p.name);group=os.getpgid(pid);cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
                if group in r['vacated_pgids']:conflicts.append(pid)
                if cmd.startswith(('ssh ','sshd:','rsync ')):continue
                if any(x in cmd for x in ('/k2-20261010','/k-v2-20261010-r1/',str(G)+'/',str(j.parent/'eval-ops/pool_regret.py'),str(j.parent/'eval-ops/regret_game.py'))):conflicts.append(pid)
                if 'exit-r2' in cmd and any(x in cmd for x in ('/game_pool','/game_worker','/postkill','/descriptive')):conflicts.append(pid)
                if str(j)+'/' in cmd:
                    for thread in (p/'task').iterdir():
                        tid=int(thread.name)
                        if os.getpriority(os.PRIO_PROCESS,tid)!=10 or os.sched_getscheduler(tid)!=os.SCHED_OTHER or not os.sched_getaffinity(tid)<=set(range(56)):conflicts.append(pid)
            except (FileNotFoundError,ProcessLookupError):pass
            except (PermissionError,OSError):conflicts.append(int(p.name))
        _conflicts=conflicts;_checked=time.monotonic()
    available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
    return not _conflicts and available>=24*2**30


def frozen(j):
    f=json.loads((j/'evaluation-freeze.json').read_text());p=json.loads((j/'evaluation-prelaunch.json').read_text())
    assert p['pushed'] and p['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json')
    assert f['protocol']=='r1(b)-coarse-first-W-200ms' and f['timing_host']=='127x03'
    assert f['physical_cores']==list(range(56))
    for name,want in f['files'].items():assert sha(j/name)==want,name
    return f
