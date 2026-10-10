"""Meter controller-admission qualification on core63, without evaluations."""
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
    assert socket.gethostname().split('.')[0]=='127x03' and os.sched_getaffinity(0)=={63}
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getscheduler(0)==os.SCHED_IDLE
    started=time.monotonic()
    names=('evaluation_k_yield.py','controller_k_yield.py','test_evaluation_k_yield.py','qualify_evaluation_k_yield.py')
    for name in names:ast.parse((j/'ops'/name).read_text())
    rc=subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',str(j/'ops/test_evaluation_k_yield.py')]).returncode
    u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
    write_json(j/'k-v2-yield-qualification.json',dict(passed=rc==0,tests=8,exit_code=rc,
        utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),files={name:sha(j/'ops'/name) for name in names},
        parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,
        wall_seconds=time.monotonic()-started,no_games=True,no_real_G_stop=True,
        scope='Core63 metadata-only controller tests; fake K/G files/processes. No stage1/2 scoring or game evaluation.'))
    if rc:raise SystemExit(rc)

if __name__=='__main__':main()
