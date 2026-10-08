"""Detached hub continuation: release -> freeze -> checked lease copies -> runs.

Never evaluates held-out data or modifies another task's files. Refuses to
duplicate a recorded launch. Manual recovery inspects receipts before retry.
"""
from datetime import datetime,timezone
import argparse
import json
from pathlib import Path
import shlex
import socket
import subprocess
import time

ROOT=Path('/mpac/sdicks02/repos/clasher')
DATA=ROOT/'reports/strategy_council_20260928/imitation/data'
OWN=ROOT/'imitation/t11'
LEASE=Path('/mpac/sdicks02/repos/clasher-lease')
WORK=LEASE/'t11-20261008-v1'
STATE=OWN/'receipts/pipeline-state.json'


def run(argv):
    return subprocess.check_output([str(x) for x in argv],text=True)


def ssh(host,script):
    return run(['ssh','-o','BatchMode=yes',host,'bash','-c',shlex.quote(script)])


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def mirror():
    run(['rsync','-cr',str(OWN/'receipts')+'/', '127x05:'+str(OWN/'receipts')+'/'])
    if (ROOT/'imitation/gate-a-v2/freeze.json').exists():
        run(['rsync','-c',*[str(ROOT/'imitation/gate-a-v2'/n) for n in ('PREREG.md','freeze.json','executable-manifest.json')],
             '127x05:'+str(ROOT/'imitation/gate-a-v2')+'/'])
    if (DATA/'receipts/T11-STORE-PASS.json').exists():
        run(['rsync','-c',str(DATA/'receipts/T11-STORE-PASS.json'),'127x05:'+str(DATA/'receipts')+'/'])


def main():
    assert socket.gethostname()=='127x01'
    p=argparse.ArgumentParser();p.add_argument('--finish-label',default='t11-store-finish-20261008-r1');a=p.parse_args()
    if STATE.exists():
        raise ValueError('pipeline state exists: inspect active labels; no automatic duplicate launch')
    state=dict(started_at=datetime.now(timezone.utc).isoformat(),stage='waiting_store',hosts={},training_started=False,finish_label=a.finish_label)
    write(STATE,state)
    try:
        finish=Path('/mpac/sdicks02/jobs/clasher')/(a.finish_label+'.exit')
        while not finish.exists():
            assert datetime.now(timezone.utc)<datetime.fromisoformat('2026-10-09T03:30:00+00:00')
            time.sleep(30)
        assert finish.read_text().strip()=='0','store finish failed'
        assert json.loads((OWN/'receipts/adapter-validation.json').read_text())['passed']
        state['stage']='freezing';write(STATE,state)
        print(run([ROOT/'.venv/bin/python','-B',OWN/'freeze.py']),flush=True)
        state['stage']='copies';write(STATE,state);mirror()
        for host,seed in [('127x16',2026100821),('127x18',2026100822)]:
            live=json.loads(ssh(host,'cat /mpac/sdicks02/fleet-leases/'+host+'.json'))
            assert live['project']=='clasher' and live['gpu'] and not live.get('reclaim') and not live.get('refused')
            assert datetime.fromisoformat(live['expected_end_utc'].replace('Z','+00:00'))>datetime.now(timezone.utc)
            ssh(host,shlex.join(['mkdir','-p',str(WORK/'operations')]))
            run(['rsync','-c',str(OWN/'copy_store.py'),host+':'+str(WORK/'operations')+'/'])
            label='t11-v2-store-copy-'+host+'-v1'
            command='source '+str(LEASE/'env.sh')+' && '+shlex.join(['bash',str(LEASE/'run.sh'),label,
                     str(LEASE/'repo/.venv/bin/python'),'-B',str(WORK/'operations/copy_store.py')])
            state['hosts'][host]=dict(seed=seed,copy_label=label,copy_command=command,copy_launch=ssh(host,command),stage='copying')
            write(STATE,state);mirror()
        while any(x['stage']!='training' for x in state['hosts'].values()):
            assert datetime.now(timezone.utc)<datetime.fromisoformat('2026-10-09T04:00:00+00:00')
            for host,h in state['hosts'].items():
                if h['stage']=='training':continue
                exit_path=LEASE/'jobs'/(h['copy_label']+'.exit.json')
                raw=ssh(host,'if [ -f '+shlex.quote(str(exit_path))+' ]; then cat '+shlex.quote(str(exit_path))+'; fi')
                if not raw.strip():continue
                exit_info=json.loads(raw)
                assert exit_info.get('exit_code',exit_info.get('returncode'))==0,exit_info
                copy=json.loads(ssh(host,'cat '+str(WORK/'copy-receipt.json')));assert copy['passed']
                write(OWN/'receipts'/('copy-'+host+'.json'),copy)
                source=WORK/'source'
                preflight='source '+str(LEASE/'env.sh')+' && cd '+str(source)+' && '+shlex.join(['env','PYTHONPATH='+str(source),
                    str(LEASE/'envs/clasher-gpu/bin/python'),'-B','-m','imitation.t11.preflight'])
                ready=json.loads(ssh(host,preflight));assert ready['passed'];write(OWN/'receipts'/('preflight-'+host+'.json'),ready)
                seed=h['seed'];label='t11-v2-main-'+str(seed)+'-v1';output=WORK/'runs'/('main-'+str(seed))
                argv=[str(LEASE/'envs/clasher-gpu/bin/python'),'-B','-m','imitation.t11.train',
                      '--freeze',str(source/'imitation/gate-a-v2/executable-manifest.json'),
                      '--store',str(LEASE/'data/v2-store-v1/train'),'--dev',str(LEASE/'data/v2-store-v1/dev'),
                      '--assets',str(WORK/'inputs/assets.npz'),'--qualification',str(WORK/'inputs/T11-STORE-PASS.json'),
                      '--output',str(output),'--seed',str(seed),'--epochs','6','--batch-size','8192','--microbatch','7168',
                      '--workers','1','--tile-width','64','--warmup','2000','--patience','3','--checkpoint-every','1000',
                      '--device','cuda','--stop-at','2026-10-09T04:20:00Z']
                inner='cd '+shlex.quote(str(source))+' && exec '+shlex.join(['env','PYTHONPATH='+str(source),*argv])
                command='source '+str(LEASE/'env.sh')+' && '+shlex.join(['bash',str(LEASE/'run.sh'),label,'bash','-c',inner])
                h.update(stage='launch_pending',label=label,trainer_argv=argv,source=str(source),output=str(output),command=command)
                write(STATE,state);mirror() # durable launch intent before side effect
                h['launch_response']=ssh(host,command);h['stage']='training';h['launched_at']=datetime.now(timezone.utc).isoformat()
                state['training_started']=True;write(STATE,state);mirror()
            if any(x['stage']!='training' for x in state['hosts'].values()):time.sleep(30)
        state['stage']='both_launched';state['ended_at']=datetime.now(timezone.utc).isoformat();write(STATE,state);mirror()
        print(json.dumps(state),flush=True)
    except BaseException as error:
        state['failure']=repr(error);state['failed_at']=datetime.now(timezone.utc).isoformat();write(STATE,state)
        mirror();raise


if __name__=='__main__':main()
