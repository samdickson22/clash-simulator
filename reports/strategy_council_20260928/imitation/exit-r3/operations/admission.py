"""Explicit coordinator CPU release receipt plus live no-K2/no-X/no-G checks."""
import hashlib,json,os,socket,time
from pathlib import Path

def context():
    return dict(host=socket.gethostname().split('.')[0],affinity=sorted(os.sched_getaffinity(0)),nice=os.getpriority(os.PRIO_PROCESS,0),scheduler=os.sched_getscheduler(0))

def active_conflicts():
    conflicts=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            cmd=(proc/'cmdline').read_bytes().replace(b'\x00',b' ').decode(errors='replace')
            if cmd.startswith(('ssh ','sshd:','rsync ')):continue
            if any(v in cmd for v in ('/k2-20261010','reports/explore/k2/run.py','/exit-g-topup-20261010/ops/','/k-v2-20261010-r1/')):
                conflicts.append(dict(pid=int(proc.name),command=cmd[:600]))
            if 'exit-r2' in cmd and any(v in cmd for v in ('/game_pool','/game_worker','/stage3_block_worker','/postkill','/descriptive')):
                conflicts.append(dict(pid=int(proc.name),command=cmd[:600]))
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    return conflicts

_conflict_cache_time=0.;_conflict_cache=[]

def allowed(job):
    global _conflict_cache_time,_conflict_cache
    j=Path(job);c=context()
    if c['host'] not in ('127x01','127x03') or c['nice']!=10 or c['scheduler']!=os.SCHED_OTHER:return False
    limit=60 if c['host']=='127x03' else 40
    if not set(c['affinity'])<=set(range(limit)):return False
    if (j/'REPORTING.STOP').exists() or (j/'REGRET.STOP').exists() or time.time()>=1791695700:return False
    receipt=j/'CPU-RELEASE-ADMITTED.json'
    if not receipt.exists():return False
    r=json.loads(receipt.read_text())
    if not r.get('explicit_release') or r.get('host')!=c['host'] or not r.get('release_evidence_sha256'):return False
    evidence=j/r.get('release_evidence_path','CPU-RELEASE-EVIDENCE.json')
    if not evidence.exists() or hashlib.sha256(evidence.read_bytes()).hexdigest()!=r['release_evidence_sha256']:return False
    if time.monotonic()-_conflict_cache_time>=10:
        _conflict_cache=active_conflicts()
        for proc in Path('/proc').iterdir():
            if proc.name.isdigit():
                try:
                    if os.getpgid(int(proc.name)) in r.get('vacated_pgids',[]):_conflict_cache.append(dict(pid=int(proc.name),reason='released owner PGID still active'))
                except (ProcessLookupError,PermissionError):pass
        _conflict_cache_time=time.monotonic()
    available=int(next(v.split()[1] for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith('MemAvailable:')))*1024
    return available>=24*2**30 and not _conflict_cache
