"""Metadata-only, home03/core63 qualification; no model/game evaluation."""
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
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);j=Path(p.parse_args().job)
    assert socket.gethostname().split('.')[0]=='127x03' and os.sched_getaffinity(0)=={63}
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getscheduler(0)==os.SCHED_IDLE
    started=time.monotonic();names=['controller_offline_record.py','test_offline_record.py','qualify_offline_record.py']
    for name in names:ast.parse((j/'ops'/name).read_text())
    rc=subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',str(j/'ops/test_offline_record.py')]).returncode
    own=resource.getrusage(resource.RUSAGE_SELF);kids=resource.getrusage(resource.RUSAGE_CHILDREN)
    write_json(j/f'offline-record-qualification-{os.getpid()}.json',dict(
        utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),passed=rc==0,tests=6,
        files={name:sha(j/'ops'/name) for name in names},exit_code=rc,
        parent_cpu_seconds=own.ru_utime+own.ru_stime,children_cpu_seconds=kids.ru_utime+kids.ru_stime,
        wall_seconds=time.monotonic()-started,no_games=True,no_policy_or_checkpoint_load=True))
    if rc:raise SystemExit(rc)

if __name__=='__main__':main()
