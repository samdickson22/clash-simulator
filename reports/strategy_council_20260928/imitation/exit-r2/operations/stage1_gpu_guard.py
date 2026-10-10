"""Metadata/resource guards for GPU-only heldout scoring, never simulations."""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
from datetime import datetime, timezone

HOSTS={'X1':'127x09','X2':'127x16','X3':'127x08','X4':'127x01','X5':'127x04','X6':'127x13','X7':'127x14'}
LEASED={'127x09','127x13','127x14','127x16'}

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1<<20),b''):h.update(data)
    return h.hexdigest()

def verify_amendment(job):
    a=json.loads((job/'stage1-gpu-amendment.json').read_text())
    p=json.loads((job/'stage1-gpu-prelaunch.json').read_text())
    assert a['committed_before_runs'] and p['pushed']
    assert p['amendment_sha256']==digest(job/'stage1-gpu-amendment.json')
    for name,want in a['files'].items():assert digest(job/name)==want,name
    q=json.loads((job/'stage1-gpu-qualification.json').read_text())
    assert q['passed'] and digest(job/'stage1-gpu-qualification.json')==a['qualification_sha256']
    return a

def quiet08(path=None):
    path=Path(path) if path else Path.home()/'.config/fleet-top/quiet'
    return path.exists() and any(re.search(r'(?<!\d)(?:127x)?08(?!\d)',line.split('#',1)[0]) for line in path.read_text().splitlines())

def own_tree(pid):
    out=[pid]
    for p in out:
        try:out.extend(map(int,Path(f'/proc/{p}/task/{p}/children').read_text().split()))
        except FileNotFoundError:pass
    return out

def resources(pids):
    pss=0
    for pid in pids:
        try:pss+=int(next(s.split()[1] for s in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines() if s.startswith('Pss:')))*1024
        except (FileNotFoundError,ProcessLookupError):pass
    free=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())*2**20
    return dict(pss_bytes=pss,gpu_free_bytes=free,processes=len(pids))

def guard(job,arm):
    host=socket.gethostname().split('.')[0]
    assert host==HOSTS[arm],(arm,host)
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getscheduler(0)==os.SCHED_IDLE
    if (job/'REPORTING.STOP').exists() or (job/f'STAGE1-{arm}.STOP').exists() or time.time()>=1791696000:
        raise InterruptedError('owned scoring stop/deadline')
    if host=='127x08' and (quiet08() or time.time()>=1791609300 or (job/'FIT.STOP').exists()):
        raise InterruptedError('08 quiet/reclaim/Oct10 05:15Z guard: vacate before05:30Z')
    if host in LEASED:
        d=json.loads(Path(f'/mpac/sdicks02/fleet-leases/{host}.json').read_text())
        assert d['project']=='clasher' and d.get('gpu') and not d.get('reclaim') and not d.get('refused')
        assert datetime.fromisoformat(d['expected_end_utc'].replace('Z','+00:00'))>datetime.now(timezone.utc)
