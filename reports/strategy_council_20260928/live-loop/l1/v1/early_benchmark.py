"""Release the completed primary emulator while the second shard finishes."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT))
from scripts.run_l1_v1_pipeline import V1,run,stop_owned,progress
pid=73610
deadline=time.monotonic()+240
while not (V1/'dataset/complete.json').exists():
    if time.monotonic()>deadline:raise TimeoutError('Primary shard did not finish')
    time.sleep(2)
assert not (V1/'dataset-merged').exists()
command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
assert 'scripts/run_l1_v1_pipeline.py' in command
os.kill(pid,signal.SIGSTOP)
try:
    progress('Temporarily suspended the owned waiting pipeline for an early primary stream benchmark; secondary collection continues.')
    run('stream-benchmark',['scripts/benchmark_l1_stream.py','--ownership',V1/'emulator-grpc-auth2/complete.json',
        '--dataset',V1/'dataset','--proto',V1/'grpc','--output',V1/'stream-timing.json'])
    stop_owned(V1/'emulator-grpc-auth2')
finally:
    command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
    assert 'scripts/run_l1_v1_pipeline.py' in command
    os.kill(pid,signal.SIGCONT)
    progress('Resumed owned pipeline after early benchmark. Existing stage receipt prevents duplicate benchmark work.')
