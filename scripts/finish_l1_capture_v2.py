"""Finish the already-running owned capture without launching another driver."""
import json
import subprocess
import time
import argparse

from run_l1_events_v2 import V2
from run_l1_v1_pipeline import stop_owned
from collect_l1_rendered import progress


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--collector-pid',type=int)
    a=p.parse_args()
    pid=a.collector_pid or json.loads((V2/'fast-stream-dataset/active-process.json').read_text())['pid']
    deadline=time.monotonic()+1800
    while not (V2/'fast-stream-dataset/complete.json').exists():
        running=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True)
        if running.returncode or 'collect_l1_stream_v2.py --mode event-boundaries' not in running.stdout or str(V2/'fast-stream-dataset') not in running.stdout:
            raise RuntimeError('Owned event-boundary collector ended without completion')
        if time.monotonic()>deadline:raise TimeoutError('Event-boundary capture deadline')
        time.sleep(5)
    stop_owned(V2/'emulator')
    (V2/'stream-pipeline-complete.json').write_text(json.dumps(dict(at=time.time(),status='capture_only',
        scope='Both capture diagnostics and full tail windows complete; event-boundary stream scoring is separate'))+'\n')
    progress('v2 all owned captures complete; emulator stopped. Single-tick pacing data is an unscored diagnostic. Frozen event-boundary inference remains queued.')


if __name__=='__main__':main()
