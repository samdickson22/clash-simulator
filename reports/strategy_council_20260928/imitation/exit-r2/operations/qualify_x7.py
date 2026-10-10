"""Meter X7 composition/family/stub-shell qualification on home03 core63."""
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

NAMES=('experiment_x7.py','stage_x7.py','supervise_x7.py','offline_x7.py',
       'game_worker_x7.py','game_pool_x7.py','controller_x7.py','fit_collection_ready_x7.py',
       'stage3_sdefault_admission_x7.py','game_pool_sdefault_x7.py',
       'stage3_block_worker_x7.py','game_worker_sdefault_x7.py','reduce_stage3_sdefault_x7.py',
       'test_x7_admission.py','qualify_x7.py','run_fit_x7.sh')

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);j=Path(p.parse_args().job)
    assert socket.gethostname().split('.')[0]=='127x03' and os.sched_getaffinity(0)=={63}
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getscheduler(0)==os.SCHED_IDLE
    start=time.monotonic()
    for name in NAMES:
        if name.endswith('.py'):ast.parse((j/'ops'/name).read_text())
    subprocess.run(['bash','-n',str(j/'ops/run_fit_x7.sh')],check=True)
    rc=subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',str(j/'ops/test_x7_admission.py')]).returncode
    own,kids=resource.getrusage(resource.RUSAGE_SELF),resource.getrusage(resource.RUSAGE_CHILDREN)
    write_json(j/f'x7-qualification-{os.getpid()}.json',dict(
        utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),passed=rc==0,tests=10,
        exit_code=rc,files={name:sha(j/'ops'/name) for name in NAMES},
        parent_cpu_seconds=own.ru_utime+own.ru_stime,children_cpu_seconds=kids.ru_utime+kids.ru_stime,
        wall_seconds=time.monotonic()-start,no_games=True,no_real_policy_or_checkpoint_load=True,
        scope='Core63 fake metadata and Python-stub shell invocation; preserves original default-layer/block qualifications'))
    if rc:raise SystemExit(rc)

if __name__=='__main__':main()
