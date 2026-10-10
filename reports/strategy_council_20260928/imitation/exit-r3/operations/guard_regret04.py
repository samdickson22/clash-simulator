"""Regret-only coordinator slot; no timing-game admission on04."""
import hashlib,json,os,socket,time
from pathlib import Path
DEADLINE=1791617400 # 2026-10-10T07:30:00Z; coordinator clarification
STOP_LEAD_SECONDS=10 # Allow SSH polling and owned child reaping before vacancy.

def full_pressure():
    line=next(l for l in Path('/proc/pressure/memory').read_text().splitlines() if l.startswith('full '))
    return float(next(v.split('=')[1] for v in line.split() if v.startswith('avg10=')))

def conflicts():
    found=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            cmd=(p/'cmdline').read_bytes().replace(b'\x00',b' ').decode(errors='replace')
            if cmd.startswith(('ssh ','sshd:','rsync ')):continue
            if any(v in cmd.lower() for v in ('amendment19','parallel_body','body_verification_pool','body_verification_launcher','run_body_epoch_v4','a19-')):
                found.append(int(p.name))
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    return found

def allowed(job,manager=False):
    j=Path(job)
    if socket.gethostname().split('.')[0]!='127x04' or os.getpriority(os.PRIO_PROCESS,0)!=19 or os.sched_getscheduler(0)!=os.SCHED_OTHER:return False
    if not set(os.sched_getaffinity(0))<=set(range(12,20)):return False
    if time.time()>=DEADLINE-STOP_LEAD_SECONDS or (j/'REGRET04.STOP').exists() or (j/'REGRET.STOP').exists() or full_pressure()>10:return False
    receipt=j/'REGRET04-ADMITTED.json';authority=j/'REGRET04-AUTHORITY.json'
    if not receipt.exists() or not authority.exists():return False
    r=json.loads(receipt.read_text())
    if r.get('host')!='127x04' or not r.get('regret_only') or r.get('authority_sha256')!=hashlib.sha256(authority.read_bytes()).hexdigest():return False
    if conflicts():return False
    if not manager:
        heartbeat=j/'REGRET04-HEARTBEAT.json'
        if not heartbeat.exists():return False
        h=json.loads(heartbeat.read_text())
        if not h['allowed'] or time.time()-h['checked_epoch']>6:return False
    return True
