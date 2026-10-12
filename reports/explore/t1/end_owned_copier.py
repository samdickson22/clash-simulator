"""Candidate END transport adapter; independent approval required before use.

Runs only on untimed 05. Frozen mirror.register/transport_prefix provide identity
and OP-6 transport attribution. Copies measurement bytes privately; never reduces
scientific data. No reporting game artifacts or remote commands except rsync.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import time


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def put(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, sort_keys=True) + '\n')
    temporary.replace(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--job', type=Path, required=True)
    p.add_argument('--host', choices=('127x01', '127x08'), required=True)
    p.add_argument('--frozen-modules', type=Path, required=True)
    p.add_argument('--module-pins', type=Path, required=True)
    a = p.parse_args()
    assert socket.gethostname() == '127x05'
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert os.sched_getaffinity(0) == {63}
    assert a.job.is_absolute() and a.job == a.job.resolve()
    assert a.job.is_dir() and not (a.job / 'owned-copier-admission.json').exists()
    pins = json.loads(a.module_pins.read_text())
    assert pins['source_commit'] == 'aeeb3003'
    for name, expected in pins['files'].items():
        assert '/' not in name and digest(a.frozen_modules / name) == expected
    sys.path.insert(0, str(a.frozen_modules))
    from mirror import register, transport_prefix
    register(a.job, [a.host], 'END')
    put(a.job / 'COPIER-READY.json', dict(utc=time.time(), host=a.host,
                                       pid=os.getpid(), registered=True))
    while not (a.job / 'GO-COPY').exists():
        if (a.job / 'STOP-COPY').exists():
            return
        time.sleep(1)
    dest = a.job / 'durable-measurement'
    dest.mkdir(mode=0o700)
    source = f'{a.host}:{a.job}/measurement/'
    names = ('capacity.jsonl', 'guard-admission.json', 'guard-blocks.jsonl',
             'failure.json', 'cleanup-failure.json', 'receipt-manifest.json',
             'receipt-manifest.sha256', 'tiers-complete.json')
    base = ['rsync', '-a', '--rsync-path',
            shlex.join(transport_prefix(a.job) + ['rsync'])]
    seen = False
    while not (a.job / 'STOP-COPY').exists():
        try:
            command = base + ['--append-verify']
            for name in names:
                command += ['--include', '/' + name]
            command += ['--exclude', '*', source, str(dest) + '/']
            result = subprocess.run(command, timeout=30, capture_output=True)
            # Exclusive measurement root is created by E4 after detached launch.
            if result.returncode == 23 and not seen and not list(dest.iterdir()):
                time.sleep(10)
                continue
            if result.returncode:
                raise RuntimeError(f'health rsync exit {result.returncode}')
            seen = True
            put(a.job / 'copy-health.json', dict(utc=time.time(), host=a.host,
                transport_ok=True, sealed=(dest / 'receipt-manifest.sha256').exists()))
            if (dest / 'receipt-manifest.sha256').exists():
                subprocess.run(base + [source, str(dest) + '/'],
                               timeout=900, check=True, capture_output=True)
                seal = dest / 'receipt-manifest.json'
                expected = (dest / 'receipt-manifest.sha256').read_text().split()
                assert expected == [digest(seal), 'receipt-manifest.json']
                manifest = json.loads(seal.read_text())
                assert manifest['files']
                for name, wanted in manifest['files'].items():
                    target = (dest / name).resolve()
                    assert target.is_relative_to(dest.resolve())
                    assert target.is_file() and digest(target) == wanted
                put(a.job / 'DURABLE-ACK.json', dict(utc=time.time(), host=a.host,
                    receipt_manifest_sha256=digest(seal), files=len(manifest['files']),
                    status=manifest['status'], all_hashes_verified=True, outcomes_sealed=True))
                return
        except Exception as error:
            put(a.job / 'COPY-FAULT.json', dict(utc=time.time(), host=a.host,
                error=type(error).__name__ + ': ' + str(error), outcomes_sealed=True))
            raise
        time.sleep(10)


if __name__ == '__main__':
    main()
