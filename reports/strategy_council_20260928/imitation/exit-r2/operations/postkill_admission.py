"""Separate fresh-seed exploration; NEVER ADOPTABLE. Admission on01 only."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from imitation.exit_r1.rows import sha,write_json
from experiment_x7 import load_experiment
BASE=4503602007370496
SMOKE_BASE=4503602017370496
G_ROOT=Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010')
LABEL=dict(lane='exploration; never adoptable',never_adoptable=True,adoption_eligible=False)

def labelled(value):
    value.update(LABEL);return value

def frozen(job):
    h=json.loads((job/'postkill-sdefault-addendum.json').read_text())
    assert h['kind']=='post-kill S-default; exploration; never adoptable'
    assert h['never_adoptable'] and not h['adoption_eligible'] and h['committed_before_games']
    receipt=json.loads((job/'postkill-sdefault-prelaunch.json').read_text())
    assert receipt['pushed'] and receipt['addendum_sha256']==sha(job/'postkill-sdefault-addendum.json')
    assert h['base_freeze_sha256']==sha(job/'freeze.json')
    assert sha(job/'postkill-seed-audit.json')==h['seed_audit_sha256']
    assert json.loads((job/'postkill-seed-audit.json').read_text())['passed']
    for relative,expected in h['files'].items():assert sha(job/relative)==expected,relative
    qual=json.loads((job/'sdefault-qualification.json').read_text())
    assert qual['passed'] and sha(job/'sdefault-qualification.json')==h['default_layer_qualification_sha256']
    for name,expected in qual['files'].items():assert sha(job/'ops'/name)==expected,name
    tests=json.loads((job/'postkill-code-qualification.json').read_text())
    assert tests['passed'] and sha(job/'postkill-code-qualification.json')==h['code_qualification_sha256']
    return h

def chosen_from_results(results):
    assert set(results)=={'X'+str(i) for i in range(1,8)},'All seven final offline results required'
    best=min(('X'+str(i) for i in range(3,8)),key=lambda arm:(-results[arm]['teacher']['metrics']['play_recall']['value'],int(arm[1:])))
    return ['X1','X2',best]

def selection(job):
    results={arm:json.loads((job/'offline'/f'{arm}.json').read_text()) for arm in load_experiment(job)['arms']}
    selected=chosen_from_results(results)
    seal=json.loads((job/'postkill-selection.json').read_text())
    receipt=json.loads((job/'postkill-selection-prelaunch.json').read_text())
    assert receipt['pushed'] and receipt['selection_sha256']==sha(job/'postkill-selection.json')
    assert seal['selected']==selected and seal['harness_sha256']==sha(job/'postkill-sdefault-addendum.json')
    for arm,value in results.items():
        assert seal['offline_sha256'][arm]==sha(job/'offline'/f'{arm}.json')
        assert seal['checkpoint_sha256'][arm]==value['checkpoint_sha256']
    return selected

def context():
    assert socket.gethostname().split('.')[0]=='127x01'
    assert os.getpriority(os.PRIO_PROCESS,0)==10
    assert os.sched_getscheduler(0)==os.SCHED_OTHER
    return dict(host='127x01',affinity=sorted(os.sched_getaffinity(0)),scheduler='SCHED_OTHER',nice=10,torch_threads=1)

def load_receipt():
    available=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024
    return labelled(dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),mem_available_bytes=available,load1=os.getloadavg()[0]))

def quiet_g_processes():
    output=subprocess.check_output(['ps','-eo','pid=,pgid=,args='],text=True)
    return [line.strip() for line in output.splitlines() if str(G_ROOT/'ops')+'/' in line]

def x4_exited(job):
    from fit_collection_ready import snapshot
    return snapshot(job,'X4',4883)['ready']

def allowed(job):
    context()
    if (job/'POSTKILL.STOP').exists() or time.time()>=1791696000:return False
    if not x4_exited(job) or not (G_ROOT/'STOP-01').exists() or quiet_g_processes():return False
    load=load_receipt();return load['mem_available_bytes']>=24*2**30 and load['load1']<=100

def admission(job,task,state):
    context()
    assert (G_ROOT/'STOP-01').exists(),'Coordinator G STOP-01 must remain present'
    live=quiet_g_processes()
    if live:state.pop('empty_since',None)
    else:state.setdefault('empty_since',time.monotonic())
    admitted=not live and time.monotonic()-state['empty_since']>=1 and allowed(job)
    write_json(job/'postkill-admission.json',labelled(dict(task=task,admitted=admitted,g_processes=live,load=load_receipt(),rule='01 only after X4 final clean exit; existing G STOP and full drain/two empty scans; physical0-39/nice10/SCHED_OTHER/Torch1')))
    return admitted

def arm_order(arms,index):
    offset=index%len(arms);return arms[offset:]+arms[:offset]
