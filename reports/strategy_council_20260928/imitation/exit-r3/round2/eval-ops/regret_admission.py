"""Regret-only home03 admission after K2 explicit release; no timing games."""
import json,os,time
from pathlib import Path
from admission import context,sha
G=Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010')
_checked=0.;_conflicts=[]
def allowed(job):
    global _checked,_conflicts
    j=Path(job);c=context()
    if c['host']!='127x03' or c['nice']!=10 or c['scheduler']!=os.SCHED_OTHER or not set(c['affinity'])<=set(range(60)):return False
    if time.time()>=1791695700 or any((j/s).exists() for s in ('REGRET.STOP','EVAL.STOP')) or not (G/'STOP-03').exists():return False
    p=j/'REGRET-CPU-ADMITTED.json'
    if not p.exists():return False
    r=json.loads(p.read_text());e=j/'REGRET-CPU-EVIDENCE.json'
    if not r['explicit_release'] or r['host']!='127x03' or sha(e)!=r['evidence_sha256']:return False
    if time.monotonic()-_checked>=5:
        conflicts=[]
        for p in Path('/proc').iterdir():
            if not p.name.isdigit():continue
            try:
                pid=int(p.name);cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
                if os.getpgid(pid) in r['vacated_pgids']:conflicts.append(pid)
                if cmd.startswith(('ssh ','sshd:','rsync ')):continue
                if any(s in cmd for s in ('/k2-20261010','/k-v2-20261010-r1/',str(G/'ops')+'/')) or ('exit-r2' in cmd and any(s in cmd for s in ('/game_pool','/game_worker','/postkill','/descriptive'))):conflicts.append(pid)
            except (FileNotFoundError,ProcessLookupError,PermissionError):pass
        _conflicts=conflicts;_checked=time.monotonic()
    available=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024
    return not _conflicts and available>=24*2**30
def frozen(j):
    f=json.loads((j/'evaluation-freeze.json').read_text());p=json.loads((j/'evaluation-prelaunch.json').read_text());assert p['pushed'] and p['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json')
    files=dict(f['files']);files.update(f['regret_files'])
    for name,want in files.items():assert sha(j/name)==want,name
    return f
