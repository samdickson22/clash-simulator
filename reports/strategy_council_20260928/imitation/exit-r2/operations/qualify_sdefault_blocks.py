"""Metered home03 syntax, admission and argmax qualification; no games."""
import argparse
import ast
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import time
from imitation.exit_r1.rows import sha,write_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);a=p.parse_args();j=Path(a.job)
    assert socket.gethostname().split('.')[0]=='127x03' and os.sched_getaffinity(0)=={60}
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getscheduler(0)==os.SCHED_IDLE
    start=time.monotonic()
    files=('stage3_sdefault_admission.py','game_worker_sdefault.py','stage3_block_worker.py',
        'game_pool_sdefault.py','reduce_stage3_sdefault.py','test_sdefault_blocks.py','qualify_sdefault_blocks.py')
    for name in files:ast.parse((j/'ops'/name).read_text())
    command=[sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',str(j/'ops/test_sdefault_blocks.py')]
    rc=subprocess.run(command).returncode
    u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
    write_json(j/'sdefault-blocks-qualification.json',dict(passed=rc==0,tests=7,exit_code=rc,
        utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),no_game_seeds_consumed=True,
        files={name:sha(j/'ops'/name) for name in files},parent_cpu_seconds=u.ru_utime+u.ru_stime,
        children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-start))
    if rc:raise SystemExit(rc)

if __name__=='__main__':main()
