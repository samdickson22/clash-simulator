"""Score actual event-boundary streaming after owned emulator shutdown."""
import json
import time

from run_l1_events_v2 import V2,run


def main():
    deadline=time.monotonic()+7200
    while not (V2/'fast-stream-dataset/complete.json').exists() or not (V2/'emulator/stop.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Fast stream/shutdown deadline')
        time.sleep(5)
    # Avoid overlapping two MPS inference jobs and distorting the throughput audit.
    while not (V2/'stream-pipeline-complete.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Diagnostic stream scoring deadline')
        time.sleep(5)
    data=V2/'fast-stream-dataset'
    run('sample-fast-stream',['scripts/evaluate_l1_events_v2.py','--dataset',data,'--sample-split','heldout',
        '--fps','10.9141','--output',V2/'fast-stream-inputs.jsonl'])
    run('infer-fast-stream',['scripts/infer_l1_events_v2.py','--inputs',V2/'fast-stream-inputs.jsonl',
        '--image-root',data,'--model',V2/'model/last.pt','--output',V2/'inference-fast-stream'])
    run('evaluate-fast-stream',['scripts/evaluate_l1_events_v2.py','--dataset',data,'--inference',V2/'inference-fast-stream',
        '--selection',V2/'validation/selection.json','--fps','10.9141','--events-only','--output',V2/'evaluation-fast-stream'])
    (V2/'fast-stream-evaluation-complete.json').write_text(json.dumps(dict(at=time.time()))+'\n')


if __name__=='__main__':main()
