"""Finish all seven frozen offline gates; never admit original evaluation games."""
import argparse
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import time
from controller_gpu_gates import remote, write, HOSTS, collection_ready
from experiment_x7 import load_experiment
from stage1_gpu_guard import verify_amendment, digest

def verify_decision(job):
    path=job/'postkill-decision.json'
    decision=json.loads(path.read_text())
    receipt=json.loads((job/'postkill-decision-prelaunch.json').read_text())
    assert decision['kind']=='offline-record-only; separate never-adoptable study'
    assert receipt['pushed'] and receipt['decision_sha256']==digest(path)
    assert decision['original_freeze_sha256']==digest(job/'freeze.json')
    for relative,expected in decision['files'].items():
        assert digest(job/relative)==expected,relative
    return decision

def tick_offline(job,frozen,launched):
    for arm,host in HOSTS.items():
        result=job/'offline'/f'{arm}.json'
        if result.exists():continue
        state=remote(job,host,'status',1,arm)
        if state['status']=='done':
            write(result,state['result'])
            write(job/'offline'/f'{arm}-remote-meter.json',dict(host=host,**state['meter']))
        elif state['status']=='failed':
            raise RuntimeError(f'offline {arm} failed: {state}')
        elif state['status']=='not-started':
            if collection_ready(job,arm,host,frozen['arms'][arm]['steps']):
                state=remote(job,host,'start',1,arm)
                launched['offline'][arm]=dict(host=host,**state)
                write(job/'gpu-gates-launches.json',launched)
        else:
            assert state['status']=='active',state
    return {arm:json.loads((job/'offline'/f'{arm}.json').read_text())
            for arm in HOSTS if (job/'offline'/f'{arm}.json').exists()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',required=True)
    job=Path(ap.parse_args().job);start=time.monotonic();failures=[];offline={}
    assert socket.gethostname().split('.')[0]=='127x03'
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    assert os.sched_getscheduler(0)==os.SCHED_IDLE and os.sched_getaffinity(0)=={63}
    verify_amendment(job);verify_decision(job);frozen=load_experiment(job)
    path=job/'gpu-gates-launches.json'
    launched=json.loads(path.read_text()) if path.exists() else {'offline':{},'stage2':{}}
    assert not launched['stage2'],'original stage2 bank unexpectedly consumed'
    def state():
        write(job/'controller.json',dict(
            utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),
            stage='frozen offline scores complete' if len(offline)==7 else 'frozen offline record only',
            offline=offline,stage2={},active=None,
            offline_active=[arm for arm in launched['offline'] if arm not in offline],
            failures=failures,x3_priority_requested=False,
            original_stage3_unconsumed=True,R2_eligible=False,
            interpretation='Coordinator judged stage1 gates infeasible; frozen kills do not establish student quality.',
            postkill_study='separate fresh-seed exploration; never adoptable',
            wall_seconds=time.monotonic()-start))
    try:
        while not (job/'OFFLINE-CONTROLLER.STOP').exists() and time.time()<1791696000:
            offline=tick_offline(job,frozen,launched);state()
            if len(offline)==7:break
            time.sleep(15)
    except Exception as error:
        failures.append(str(error));state();raise
    finally:
        own=resource.getrusage(resource.RUSAGE_SELF);kids=resource.getrusage(resource.RUSAGE_CHILDREN)
        write(job/f'controller-offline-meter-{os.getpid()}.json',dict(
            parent_cpu_seconds=own.ru_utime+own.ru_stime,
            children_cpu_seconds=kids.ru_utime+kids.ru_stime,
            wall_seconds=time.monotonic()-start,failures=failures,
            accounting='Only local SSH/metadata descendants; remote scores separately whole-metered once.'))

if __name__=='__main__':main()
