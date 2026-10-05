"""Owned continuation at a completed-episode boundary, then frozen evaluation."""
import hashlib
import argparse
import json
from pathlib import Path
import signal
import subprocess
import time

from collect_l1_rendered import REPORT,progress

ROOT=REPORT.parents[3]
PY=ROOT/'.venv/bin/python'
V2=REPORT/'v2'
DATA=V2/'dataset'


def completed():
    path=DATA/'episodes.jsonl'
    return {json.loads(l)['episode_id'] for l in path.read_text().splitlines()} if path.exists() else set()


def run(name,args):
    progress('v2 starting '+name)
    with (V2/(name+'.log')).open('w') as log:
        p=subprocess.Popen([str(PY),*map(str,args)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        (V2/(name+'-process.json')).write_text(json.dumps(dict(pid=p.pid,args=list(map(str,args))))+'\n')
        code=p.wait()
    if code:raise RuntimeError(f'{name} exited {code}')
    progress('v2 finished '+name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collector-pid',type=int,required=True)
    args=parser.parse_args()
    manifest=json.loads((DATA/'manifest.json').read_text())
    training={m['episode_id'] for m in manifest['matches'] if m['split']=='train'}
    validation={m['episode_id'] for m in manifest['matches'] if m['split']=='validation'}
    deadline=time.monotonic()+7200
    while not training<=completed():
        if time.monotonic()>deadline:raise TimeoutError('Training capture deadline')
        time.sleep(1)
    # This PID was created by this v2 task and is checked before signalling.
    pid=args.collector_pid
    command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
    if 'collect_l1_events_v2.py' not in command or str(DATA) not in command:
        raise ValueError('Original collector identity changed')
    osignal=dict(pid=pid,command=command.strip(),reason='completed train boundary; correct acceptance tolerance for later double elixir')
    (V2/'collector-restart.json').write_text(json.dumps(osignal,indent=2)+'\n')
    signal.signal(signal.SIGTERM,signal.SIG_DFL)
    import os
    os.kill(pid,signal.SIGTERM)
    for _ in range(100):
        if subprocess.run(['kill','-0',str(pid)],capture_output=True).returncode:break
        time.sleep(.1)
    else:raise RuntimeError('Owned collector did not stop')
    partial={json.loads(l)['episode_id'] for l in (DATA/'inputs.jsonl').read_text().splitlines()}-completed()
    if partial:raise ValueError('Boundary restart caught partial episode; preserve and inspect')
    progress('v2 restarted owned collector after four completed training matches; no partial episode or action replay. Acceptance tolerance now covers six ticks of double/triple elixir regeneration.')
    collect_log=(V2/'collect-continuation.log').open('w')
    collector=subprocess.Popen([str(PY),'scripts/collect_l1_events_v2.py','--output',str(DATA)],cwd=ROOT,
                               stdout=collect_log,stderr=subprocess.STDOUT)
    (V2/'collector-continuation-process.json').write_text(json.dumps(dict(pid=collector.pid))+'\n')
    run('train-events',['scripts/train_l1_events_v2.py','--dataset',DATA,'--output',V2/'model'])
    while not validation<=completed():
        if collector.poll() is not None:raise RuntimeError('Collection ended before validation completed')
        time.sleep(5)
    run('sample-validation',['scripts/evaluate_l1_events_v2.py','--dataset',DATA,'--sample-split','validation',
        '--fps','10','--output',V2/'validation-inputs.jsonl'])
    run('infer-validation',['scripts/infer_l1_events_v2.py','--inputs',V2/'validation-inputs.jsonl',
        '--image-root',DATA,'--model',V2/'model/last.pt','--output',V2/'inference-validation'])
    run('select-validation',['scripts/evaluate_l1_events_v2.py','--dataset',DATA,'--inference',V2/'inference-validation',
        '--select','--output',V2/'validation'])
    code=collector.wait();collect_log.close()
    if code:raise RuntimeError(f'Collector exited {code}')
    for fps in ('10','10.9141','20'):
        name='heldout-'+fps
        run('sample-'+name,['scripts/evaluate_l1_events_v2.py','--dataset',DATA,'--sample-split','heldout',
            '--fps',fps,'--output',V2/(name+'-inputs.jsonl')])
        run('infer-'+name,['scripts/infer_l1_events_v2.py','--inputs',V2/(name+'-inputs.jsonl'),
            '--image-root',DATA,'--model',V2/'model/last.pt','--output',V2/('inference-'+name)])
        run('evaluate-'+name,['scripts/evaluate_l1_events_v2.py','--dataset',DATA,'--inference',V2/('inference-'+name),
            '--selection',V2/'validation/selection.json','--fps',fps,'--output',V2/('evaluation-'+name),
            *(['--corruption'] if fps=='10' else [])])
    (V2/'pipeline-complete.json').write_text(json.dumps(dict(at=time.time()))+'\n')
    progress('v2 stepped dataset, temporal fit, validation selection and three-cadence heldout evaluations completed. Continuous-stream confirmation and final audit still required.')


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        (V2/'pipeline-failure.json').write_text(json.dumps(dict(error=str(exc),at=time.time()))+'\n')
        progress('v2 pipeline stopped: '+str(exc))
        raise
