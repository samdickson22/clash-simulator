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


def check_complete(root, digest, receipt):
    attempt = json.loads((root/'attempt.json').read_text())
    if (not attempt.get('complete') or attempt.get('checkpoint_sha256') != digest
            or any(attempt.get(k) != receipt[k] for k in ['records_sha256', 'runtime_sha256'])):
        raise ValueError('incomplete or mismatched attempt')
    for dev, threads in [('cpu', 1), ('cpu', 4), ('mps', 1)]:
        d = json.loads((root/f'{dev}-t{threads}.json').read_text())
        expected = dict(checkpoint_sha256=digest, mode='session', weights='checkpoint', device=dev,
                        threads=threads, polls=20000, warmup=200, feature_hash=receipt['feature_hash'],
                        records_sha256=receipt['records_sha256'], runtime_sha256=receipt['runtime_sha256'])
        if any(d.get(k) != v for k, v in expected.items()) or d.get('total', {}).get('n') != 20000:
            raise ValueError('mismatched measurement result')


def verify_go(receipt, revision):
    if receipt.get('verdict') != 'GO' or receipt.get('revision') != revision:
        raise ValueError('no explicit GO for this revision')
    if not receipt.get('reviews'):
        raise ValueError('at least one exact-revision GO review is required')
    for review in receipt['reviews']:
        p = Path(review['path'])
        text = p.read_text()
        if (sha(p) != review['sha256'] or not re.search(r'^Verdict: GO$', text, re.M)
                or not re.search(r'^Reviewed-Revision: '+revision+r'$', text, re.M)):
            raise ValueError('GO review changed or missing')


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
    verify_go(receipt, a.revision)
    if run(['git', '-C', str(code), 'rev-parse', 'HEAD']).decode().strip() != a.revision:
        raise ValueError('code checkout is not the reviewed revision')
    run(['git', '-C', str(code), 'diff', '--exit-code', a.revision, '--', 'bot/pretrain_v1',
         'reports/bot/pretrain-v1/sweep'])
    import sys
    sys.path.insert(0, str(code))
    from bot.pretrain_v1.bench_contract import manifest_sha, runtime_sha
    if not receipt.get('records') or manifest_sha(receipt['records']) != receipt['records_sha256']:
        raise ValueError('record manifest is empty or differs from frozen identity')
    if runtime_sha() != receipt['runtime_sha256']:
        raise ValueError('runtime differs from approved receipt')
    state = dict(pid=os.getpid(), revision=a.revision, go=str(Path(a.go).resolve()),
                 source=str(SWEEP/'anchors'), output=str(out), mac_root=MAC_ROOT)
    (out/'owner.json').write_text(json.dumps(state, indent=1)+'\n')
    # Inspect exact process arguments before staging; never touch another process.
    remote = f'{MAC_ROOT}/qualification-{a.revision}'
    probe = ("import os,pathlib,shlex,subprocess; "
             "modules=['bot.'+'pretrain_v1.bench_device','bot.'+'pretrain_v1.bench_selected','bot.'+'pretrain_v1.bench_cpu']; "
             "names=['run_bench.sh','run_selected_bench.sh','bench_device.py','bench_cpu.py']; "
             "rows=subprocess.check_output(['ps','-axo','pid=,args='],text=True).splitlines(); "
             "busy=[l.split(None,1)[0] for l in rows if any(t in modules or pathlib.Path(t).name in names "
             "for t in shlex.split(l.split(None,1)[1]))]; "
             "assert not busy, 'existing Mac benchmark PIDs '+str(busy)")
    ssh(f'{MAC_PY} -B -c {shlex.quote(probe)}')
    # All destination components and archive members are checked before any Mac write. Existing code must
    # match every archived source byte; it is never extracted over a pre-existing tree or symlink.
    stage = r"""
import hashlib,io,json,pathlib,sys,tarfile
root=pathlib.Path('/Users/sam/clasher-pretrain-bench')
assert root.resolve()==root and root.is_dir(), 'benchmark root must be physical'
remote=root/('qualification-'+sys.argv[1]); code=remote/'code'
assert remote.resolve()==remote and code.resolve()==code, 'symlinked staging destination'
archive=tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()))
files={}
for member in archive.getmembers():
    p=pathlib.PurePosixPath(member.name)
    assert not p.is_absolute() and '..' not in p.parts
    assert member.isdir() or member.isfile(), 'nonregular archive member'
    if member.isfile(): files[member.name]=archive.extractfile(member).read()
if code.exists():
    assert not any(p.is_symlink() for p in code.rglob('*')), 'symlink in staged code'
    for name,data in files.items(): assert (code/name).read_bytes()==data, 'staged code changed'
else:
    remote.mkdir(exist_ok=True); code.mkdir()
    for name,data in files.items():
        p=code/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data)
record_manifest=remote/'records.json'
assert record_manifest.resolve()==record_manifest, 'symlinked manifest destination'
data=json.loads(sys.argv[2]); raw=(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n').encode()
if record_manifest.exists(): assert record_manifest.read_bytes()==raw, 'staged manifest changed'
else:
    with record_manifest.open('xb') as f: f.write(raw)
"""
    archive = run(['git', '-C', str(code), 'archive', a.revision, 'bot/pretrain_v1'])
    ssh(f'{MAC_PY} -B -c {shlex.quote(stage)} {a.revision} '+shlex.quote(json.dumps(receipt['records'])),
        payload=archive)
    # record_payloads verifies the complete consumed file set and bytes before each launch. Each measurement
    # repeats that check and parses those exact bytes, then retains the frozen identities in its output.
    verifier = (f'import sys; sys.path.insert(0,{remote+"/code"!r}); '
                'from bot.pretrain_v1.bench_contract import record_payloads,runtime_sha; '
                f'assert runtime_sha()=={receipt["runtime_sha256"]!r}; '
                f'record_payloads({MAC_ROOT+"/records-session"!r},{remote+"/records.json"!r})')
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
            check_complete(final, digest, receipt)
            log(f'{size} already completed and verified {digest}')
            continue
        ck_remote = f'{remote}/{size}-{digest}.pt'
        result_remote = f'{remote}/{size}-{digest}'
        # Upload checkpoint through a physically contained, exclusive file write. A previous identical copy
        # can be reused; symlinks and changed bytes are refused before opening a destination for writing.
        upload = ("import hashlib,pathlib,sys; p=pathlib.Path(sys.argv[1]); "
                  f"root=pathlib.Path({MAC_ROOT!r}); "
                  "assert root.resolve()==root and p.resolve()==p and root in p.parents; "
                  "raw=sys.stdin.buffer.read(); assert hashlib.sha256(raw).hexdigest()==sys.argv[2]; "
                  "assert not p.exists() or p.read_bytes()==raw; "
                  "f=None if p.exists() else p.open('xb'); "
                  "f.write(raw) if f else None; f.close() if f else None")
        ssh(f'{MAC_PY} -B -c {shlex.quote(upload)} {ck_remote} {digest}', 120, checkpoint.read_bytes())
        log(f'{size} starting {digest}; selected_admitted={d["admitted"]}')
        # A restart may find a completed remote attempt whose copy was interrupted. Recover and validate it;
        # never execute another job against an existing output directory, including a failed attempt.
        ssh(f'{MAC_PY} -B -c {shlex.quote(verifier)}')
        exists = ssh(f'if test -d {result_remote}; then echo yes; else echo no; fi').decode().strip() == 'yes'
        if not exists:
            ssh(f'{MAC_PY} -B -c {shlex.quote(probe)}')
            command = (f'cd {remote}/code && {MAC_PY} -B -m bot.pretrain_v1.bench_selected '
                       f'{ck_remote} {result_remote} {MAC_ROOT}/records-session '
                       f'--records-manifest {remote}/records.json')
            ssh(command, 5700)
        with tempfile.TemporaryDirectory(prefix=f'.{size}-copy-', dir=str(out)) as td:
            incoming = Path(td)/'result'
            run(['scp', '-rq', f'{MAC}:{result_remote}', str(incoming)], 120)
            check_complete(incoming, digest, receipt)
            (incoming/'selection.json').write_text(json.dumps(d, indent=1)+'\n')
            incoming.rename(final)
        log(f'{size} completed {digest}')
    log('all selected-checkpoint measurements completed')


if __name__ == '__main__':
    main()
