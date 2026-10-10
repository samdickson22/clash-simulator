"""Home03/core63 metadata-only distributed gate qualification and CPU meter."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import time

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',required=True);a=ap.parse_args();j=Path(a.job)
    assert socket.gethostname().split('.')[0]=='127x03' and os.sched_getaffinity(0)=={63}
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getscheduler(0)==os.SCHED_IDLE
    start=time.monotonic();names=['supplement_gpu.py','offline_gpu.py','stage1_gpu_guard.py','supervise_stage1_gpu.py','stage1_inputs.py','remote_gpu_gates.py','controller_gpu_gates.py','test_gpu_gate_admission.py','qualify_stage1_gpu.py','qualify_gpu_gate_admission.py']
    for n in names:ast.parse((j/'ops'/n).read_text(),filename=n)
    p=subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',str(j/'ops/test_gpu_gate_admission.py')],cwd=j/'source')
    own=resource.getrusage(resource.RUSAGE_SELF);kids=resource.getrusage(resource.RUSAGE_CHILDREN)
    d=dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),passed=p.returncode==0,exit_code=p.returncode,tests=12,files={n:hashlib.sha256((j/'ops'/n).read_bytes()).hexdigest() for n in names},parent_cpu_seconds=own.ru_utime+own.ru_stime,children_cpu_seconds=kids.ru_utime+kids.ru_stime,wall_seconds=time.monotonic()-start,scope='Metadata/fake attempts only; home03 core63 nice19/SCHED_IDLE, no model inference/games.')
    (j/f'gpu-gate-admission-qualification-{os.getpid()}.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(p.returncode)

if __name__=='__main__':main()
