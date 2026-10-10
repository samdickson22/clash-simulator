"""Meter only metadata readiness qualification, isolated on home03 core63."""
import argparse
import ast
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import time
from imitation.exit_r1.rows import sha, write_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--job', required=True)
    job = Path(p.parse_args().job)
    assert socket.gethostname().split('.')[0] == '127x03'
    assert os.sched_getaffinity(0) == {63}
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    assert os.sched_getscheduler(0) == os.SCHED_IDLE
    started = time.monotonic()
    names = ('fit_collection_ready.py', 'controller_ready_yield.py',
             'test_fit_collection_ready.py', 'qualify_fit_collection_ready.py')
    for name in names:
        ast.parse((job / 'ops' / name).read_text())
    rc = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                         str(job / 'ops/test_fit_collection_ready.py')]).returncode
    own, kids = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    write_json(job / f'fit-collection-qualification-{os.getpid()}.json', dict(
        utc=subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip(),
        passed=rc == 0, tests=10, exit_code=rc,
        files={name: sha(job / 'ops' / name) for name in names},
        parent_cpu_seconds=own.ru_utime + own.ru_stime,
        children_cpu_seconds=kids.ru_utime + kids.ru_stime,
        wall_seconds=time.monotonic() - started,
        no_games=True, no_policy_or_checkpoint_load=True,
        scope='Core63 metadata-only, fake fit artifacts; no scoring/evaluation or K/G intervention'))
    if rc:
        raise SystemExit(rc)


if __name__ == '__main__':
    main()
