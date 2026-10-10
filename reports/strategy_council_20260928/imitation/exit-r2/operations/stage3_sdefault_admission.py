"""Frozen S-default inputs, survivor ranking and same-load admission."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from imitation.exit_r1.rows import sha
from experiment_x6 import load_experiment

BASE=4503601517370496
SMOKE_BASE=4503601527370496
K_ROOT=Path('/mpac/sdicks02/jobs/clasher/k-v2-20261010-r1')

def frozen(job):
    h=json.loads((job/'stage3-sdefault-addendum.json').read_text())
    assert h['kind']=='S-default-K1' and h['committed_before_games']
    receipt=json.loads((job/'stage3-sdefault-prelaunch.json').read_text())
    assert receipt['pushed'] and receipt['addendum_sha256']==sha(job/'stage3-sdefault-addendum.json')
    assert h['base_freeze_sha256']==sha(job/'freeze.json')
    assert h['seed_audit_sha256']==sha(job/'stage3-sdefault-seed-audit.json')
    assert json.loads((job/'stage3-sdefault-seed-audit.json').read_text())['passed']
    for relative,expected in h['files'].items():assert sha(job/relative)==expected,relative
    qual=json.loads((job/'sdefault-qualification.json').read_text())
    assert qual['passed'] and sha(job/'sdefault-qualification.json')==h['qualification_sha256']
    for name,expected in qual['files'].items():assert sha(job/'ops'/name)==expected,name
    blocks=json.loads((job/'sdefault-blocks-qualification.json').read_text())
    assert blocks['passed'] and sha(job/'sdefault-blocks-qualification.json')==h['blocks_qualification_sha256']
    for name,expected in blocks['files'].items():assert sha(job/'ops'/name)==expected,name
    return h

def selection(job):
    arms=load_experiment(job)['arms'];survivors=[]
    for arm in arms:
        off=json.loads((job/'offline'/f'{arm}.json').read_text())
        if off['survives']:
            two=json.loads((job/'stage2'/f'{arm}.json').read_text())
            if two['survives']:survivors.append((two['loss'],-off['teacher']['metrics']['hard_action_agreement']['value'],int(arm[1:]),arm))
    return [row[-1] for row in sorted(survivors)[:3]]

def context():
    assert socket.gethostname().split('.')[0]=='127x03'
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    assert os.sched_getscheduler(0)==os.SCHED_IDLE
    return dict(host=socket.gethostname().split('.')[0],affinity=sorted(os.sched_getaffinity(0)),
                scheduler='SCHED_IDLE',nice=os.getpriority(os.PRIO_PROCESS,0),torch_threads=1)

def load_receipt():
    available=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024
    return dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),
                mem_available_bytes=available,load1=os.getloadavg()[0])

def timing_released():
    # REPORTING-DONE prevents admission in the gap between K smoke and reporting.
    if not any((K_ROOT/name).is_file() for name in ('REPORTING-DONE','REPORTING-R2-DONE')):return False
    output=subprocess.check_output(['ps','-eo','args='],text=True)
    return not any('reports/explore/k-v2/run.py' in line for line in output.splitlines())

def allowed(job):
    context()
    if (job/'REPORTING.STOP').exists() or time.time()>=1791696000:return False
    if not timing_released():return False
    return load_receipt()['mem_available_bytes']>=24*2**30

def arm_order(arms,index):
    offset=index%len(arms)
    return arms[offset:]+arms[:offset]
