#!/usr/bin/env python3
"""Dedicated 05 Mac qualification owner. Never launches training or game evaluation.

Usage: bench_wait_05.py --code ROOT --revision SHA --go RECEIPT --out DIR
The receipt freezes an explicit GO review, code revision and staged record hashes. Resume this same command;
a process lock prevents duplicate owners, and only validated completed attempts can be reused.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import time

SWEEP = Path('/mpac/sdicks02/scratch/pretrain-v1-dev/sweep')
MAC = 'macmini-fleet'
MAC_ROOT = '/Users/sam/clasher-pretrain-bench'
MAC_PY = '/Users/sam/clasher-live/venv/bin/python'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(cmd, seconds=60, payload=None):
    return subprocess.run(['timeout', str(seconds)] + cmd, input=payload, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=seconds+5, check=True).stdout


def ssh(command, seconds=60, payload=None):
    return run(['ssh', '-o', 'BatchMode=yes', MAC, command], seconds, payload)


def check_complete(root, digest, feature_hash):
    attempt = json.loads((root/'attempt.json').read_text())
    if not attempt.get('complete') or attempt.get('checkpoint_sha256') != digest:
        raise ValueError('incomplete or mismatched attempt')
    for dev, threads in [('cpu', 1), ('cpu', 4), ('mps', 1)]:
        d = json.loads((root/f'{dev}-t{threads}.json').read_text())
        expected = dict(checkpoint_sha256=digest, mode='session', weights='checkpoint', device=dev,
                        threads=threads, polls=20000, warmup=200, feature_hash=feature_hash)
        if any(d.get(k) != v for k, v in expected.items()) or d.get('total', {}).get('n') != 20000:
            raise ValueError('mismatched measurement result')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--code', required=True)
    ap.add_argument('--revision', required=True)
    ap.add_argument('--go', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    code, out = Path(a.code).resolve(), Path(a.out).resolve()
    if not re.fullmatch('[0-9a-f]{40}', a.revision):
        ap.error('revision must be a full commit SHA')
    out.mkdir(parents=True, exist_ok=True)
    lock = (SWEEP/'mac-qualification.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    def log(message):
        with (out/'waiter.log').open('a') as f:
            f.write(time.strftime('%Y-%m-%dT%H:%M:%S%z ') + message + '\n')
    receipt = json.loads(Path(a.go).read_text())
    if receipt.get('verdict') != 'GO' or receipt.get('revision') != a.revision:
        raise ValueError('no explicit GO for this revision')
    for review in receipt['reviews']:
        p = Path(review['path'])
        if sha(p) != review['sha256'] or not re.search(r'^GO\.?$', p.read_text(), re.M):
            raise ValueError('GO review changed or missing')
    if run(['git', '-C', str(code), 'rev-parse', 'HEAD']).decode().strip() != a.revision:
        raise ValueError('code checkout is not the reviewed revision')
    run(['git', '-C', str(code), 'diff', '--exit-code', a.revision, '--', 'bot/pretrain_v1',
         'reports/bot/pretrain-v1/sweep'])
    state = dict(pid=os.getpid(), revision=a.revision, go=str(Path(a.go).resolve()),
                 source=str(SWEEP/'anchors'), output=str(out), mac_root=MAC_ROOT)
    (out/'owner.json').write_text(json.dumps(state, indent=1)+'\n')
    # Inspect exact process arguments before staging; never touch another process.
    remote = f'{MAC_ROOT}/qualification-{a.revision}'
    probe = ("import os,pathlib,shlex,subprocess; "
             "modules=['bot.'+'pretrain_v1.bench_device','bot.'+'pretrain_v1.bench_selected']; "
             "names=['run_bench.sh','run_selected_bench.sh','bench_device.py','bench_cpu.py']; "
             "rows=subprocess.check_output(['ps','-axo','pid=,args='],text=True).splitlines(); "
             "busy=[l.split(None,1)[0] for l in rows if any(t in modules or pathlib.Path(t).name in names "
             "for t in shlex.split(l.split(None,1)[1]))]; "
             "assert not busy, 'existing Mac benchmark PIDs '+str(busy)")
    ssh(f'{MAC_PY} -B -c {shlex.quote(probe)}')
    ssh(f'mkdir -p {shlex.quote(remote)}')
    # Staged code is an archive of the reviewed commit, never a mutable working-tree copy.
    archive = run(['git', '-C', str(code), 'archive', a.revision, 'bot/pretrain_v1'])
    ssh(f'mkdir -p {shlex.quote(remote+"/code")} && tar -xf - -C {shlex.quote(remote+"/code")}', payload=archive)
    records = receipt['records']
    # Verify every staged input before any benchmark process starts. No replay/emulator access.
    verifier = ('import hashlib,json,pathlib; d=json.loads(' + repr(json.dumps(records)) + '); '
                'assert all(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h for p,h in d.items())')
    ssh(f'{MAC_PY} -B -c {shlex.quote(verifier)}')
    log(f'owner {os.getpid()} admitted revision {a.revision}; waiting for selected checkpoints')
    for size in ['S100', 'M', 'L']:
        final = out/size
        selection = SWEEP/'anchors'/size/'selection.json'
        while not selection.is_file():
            time.sleep(60)
        d = json.loads(selection.read_text())
        name = d['file']
        if name not in ['anchor.pt', 'PROVISIONAL-not-admitted.pt'] or d.get('smoke'):
            raise ValueError('not a selected trained checkpoint')
        checkpoint = selection.parent/name
        while not checkpoint.is_file():
            time.sleep(10)
        digest = sha(checkpoint)
        if digest != d['sha256']:
            raise ValueError(f'{size}: selected checkpoint hash mismatch')
        if final.exists():
            check_complete(final, digest, receipt['feature_hash'])
            log(f'{size} already completed and verified {digest}')
            continue
        ck_remote = f'{remote}/{size}-{digest}.pt'
        result_remote = f'{remote}/{size}-{digest}'
        run(['scp', '-q', str(checkpoint), f'{MAC}:{ck_remote}'], 120)
        log(f'{size} starting {digest}; selected_admitted={d["admitted"]}')
        # A restart may find a completed remote attempt whose copy was interrupted. Recover and validate it;
        # never execute another job against an existing output directory, including a failed attempt.
        exists = ssh(f'if test -d {result_remote}; then echo yes; else echo no; fi').decode().strip() == 'yes'
        if not exists:
            ssh(f'{MAC_PY} -B -c {shlex.quote(probe)}')
            command = (f'cd {remote}/code && {MAC_PY} -B -m bot.pretrain_v1.bench_selected '
                       f'{ck_remote} {result_remote} {MAC_ROOT}/records-session')
            ssh(command, 5700)
        with tempfile.TemporaryDirectory(prefix=f'.{size}-copy-', dir=str(out)) as td:
            incoming = Path(td)/'result'
            run(['scp', '-rq', f'{MAC}:{result_remote}', str(incoming)], 120)
            check_complete(incoming, digest, receipt['feature_hash'])
            (incoming/'selection.json').write_text(json.dumps(d, indent=1)+'\n')
            incoming.rename(final)
        log(f'{size} completed {digest}')
    log('all selected-checkpoint measurements completed')


if __name__ == '__main__':
    main()
