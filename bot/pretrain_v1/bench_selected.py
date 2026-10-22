"""Mac-only checkpoint latency runner. Arguments: CHECKPOINT OUT RECORDS --records-manifest MANIFEST.

Use a fresh output directory per attempt. An existing output directory is refused, including an incomplete
attempt. Each completed result is validated against the checkpoint, device, thread count and 20,000-poll budget.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import stat
from pathlib import Path
import subprocess
import sys


def contained(path, root):
    path = Path(path).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f'path outside benchmark directory: {path}')
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('checkpoint')
    ap.add_argument('output')
    ap.add_argument('records')
    ap.add_argument('--records-manifest', required=True)
    ap.add_argument('--load-condition', choices=['shared-load', 'canvasdoc-idle'], default='shared-load')
    a = ap.parse_args(argv)
    root = (Path.home()/'clasher-pretrain-bench').resolve()
    try:
        contained(Path.cwd(), root)
        ckpt, out, records, records_manifest = [contained(p, root) for p in
                                               (a.checkpoint, a.output, a.records, a.records_manifest)]
    except ValueError as ex:
        ap.error(str(ex))
    if not ckpt.is_file() or not records.is_dir():
        ap.error('checkpoint must exist and records must be a directory')
    fd = os.open(root/'selected-benchmark.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('benchmark lock must be a regular file')
        lock = os.fdopen(fd, 'r+')
    except BaseException:
        os.close(fd)
        raise
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    from . import featurize as F
    from .bench_contract import manifest, manifest_sha, record_payloads, runtime_sha
    record_payloads(records, records_manifest)
    records_sha256 = manifest_sha(manifest(records_manifest))
    runtime_sha256 = runtime_sha()
    sha = hashlib.sha256(ckpt.read_bytes()).hexdigest()
    # mkdir is also the exclusive attempt lock. Keep failed attempts for inspection; never silently reuse them.
    out.mkdir(parents=True, exist_ok=False)
    attempt = dict(requested_load_condition=a.load_condition, records_sha256=records_sha256, runtime_sha256=runtime_sha256, checkpoint=str(ckpt), checkpoint_sha256=sha, polls=20000, warmup=200, complete=False)
    (out/'attempt.json').write_text(json.dumps(attempt, indent=1)+'\n')
    for device, threads in [('cpu', 1), ('cpu', 4), ('mps', 1)]:
        stem = f'{device}-t{threads}'
        result = out/f'{stem}.json'
        with (out/f'{stem}.log').open('w') as log:
            subprocess.run(['perl', '-e', 'alarm shift; exec @ARGV', '1800', sys.executable, '-B', '-m',
                            'bot.pretrain_v1.bench_device', '--session', '--ckpt', str(ckpt), '--records',
                            str(records), '--device', device, '--threads', str(threads), '--polls', '20000',
                            '--warmup', '200', '--load-condition', a.load_condition, '--records-manifest', str(records_manifest), '--out', str(result)], stdout=log, stderr=subprocess.STDOUT,
                           timeout=1830, check=True)
        data = json.loads(result.read_text())
        expected = dict(requested_load_condition=a.load_condition, records_sha256=records_sha256, runtime_sha256=runtime_sha256, mode='session', weights='checkpoint', checkpoint_sha256=sha, device=device,
                        threads=threads, polls=20000, warmup=200, feature_hash=F.feature_hash())
        if (any(data.get(k) != v for k, v in expected.items()) or data.get('total', {}).get('n') != 20000
                or data.get('load_classification') != 'shared-load'
                or not data.get('canvasdoc', {}).get('complete')):
            raise RuntimeError(f'invalid benchmark result: {result}')
    attempt['complete'] = True
    (out/'attempt.json').write_text(json.dumps(attempt, indent=1)+'\n')


if __name__ == '__main__':
    main()
