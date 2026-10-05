"""Wait for owned stepped collection, capture continuous replay, and score it."""
import json
import time
import argparse
import subprocess

from run_l1_events_v2 import V2,DATA,run
from run_l1_v1_pipeline import stop_owned
from collect_l1_rendered import progress


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--resume-collector-pid',type=int)
    p.add_argument('--capture-only',action='store_true')
    a=p.parse_args()
    deadline=time.monotonic()+7200
    while not (DATA/'complete.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Stepped collection deadline')
        time.sleep(5)
    if a.resume_collector_pid:
        while not (V2/'stream-dataset/complete.json').exists():
            proc=subprocess.run(['ps','-p',str(a.resume_collector_pid),'-o','command='],capture_output=True,text=True)
            if proc.returncode or 'collect_l1_stream_v2.py' not in proc.stdout:raise RuntimeError('Owned stream collector exited without completion')
            if time.monotonic()>deadline:raise TimeoutError('Continuous collector deadline')
            time.sleep(5)
    else:
        run('collect-stream',['scripts/collect_l1_stream_v2.py'])
    run('recapture-tail',['scripts/recapture_l1_tail_v2.py'])
    stop_owned(V2/'emulator')
    if a.capture_only:
        (V2/'stream-pipeline-complete.json').write_text(json.dumps(dict(at=time.time(),status='capture_only',
            scope='Single-tick stream retained as timing diagnostic; live event gate uses event-boundary stream'))+'\n')
        progress('v2 stream capture and tail recapture complete; emulator stopped. Event-boundary replay is the live-cadence scoring dataset.')
        return
    while not (V2/'validation/selection.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Validation selection deadline')
        time.sleep(5)
    stream=V2/'stream-dataset'
    run('sample-stream',['scripts/evaluate_l1_events_v2.py','--dataset',stream,'--sample-split','heldout',
        '--fps','11','--output',V2/'stream-inputs.jsonl'])
    run('infer-stream',['scripts/infer_l1_events_v2.py','--inputs',V2/'stream-inputs.jsonl','--image-root',stream,
        '--model',V2/'model/last.pt','--output',V2/'inference-stream'])
    run('evaluate-stream',['scripts/evaluate_l1_events_v2.py','--dataset',stream,'--inference',V2/'inference-stream',
        '--selection',V2/'validation/selection.json','--fps','11','--output',V2/'evaluation-stream'])
    (V2/'stream-pipeline-complete.json').write_text(json.dumps(dict(at=time.time()))+'\n')
    progress('v2 continuous replay scored with frozen model/validation thresholds; owned emulator stopped.')


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        (V2/'stream-pipeline-failure.json').write_text(json.dumps(dict(error=str(exc),at=time.time()))+'\n')
        progress('v2 continuous pipeline stopped: '+str(exc));raise
