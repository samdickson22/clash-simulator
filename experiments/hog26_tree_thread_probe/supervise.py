"""A bounded synthetic probe alongside the unchanged production process."""

import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 2 * 1024**3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    os.chdir(ROOT)
    prefix = ROOT / 'reports/hog26_tree_thread_synthetic_probe_20260913'
    paths = [*Path(__file__).parent.glob('*.py'), ROOT / 'experiments/hog26_expanded_value_fit/value_models.py']
    native = Path('/Users/sam/.cache/clasher-margin-tree-diagnostic/sklearn/ensemble/_hist_gradient_boosting')
    paths += [*native.glob('*.py'), *native.glob('*.pyx'), *native.glob('*.so')]
    sources = {str(path): sha(path) for path in paths}
    with prefix.with_suffix('.pin.json').open('x') as stream:
        json.dump({'sources': sources, 'synthetic_only': True, 'memory_limit_bytes': LIMIT,
                   'production_change_allowed': False}, stream, indent=2)
        stream.write('\n')
    environment = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    peak, killed = 0, False
    with prefix.with_suffix('.log').open('x') as log:
        process = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                                    'experiments/hog26_tree_thread_probe/probe.py'],
                                   env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        print(json.dumps({'pid': process.pid, 'synthetic_only': True, 'limit_bytes': LIMIT}), flush=True)
        try:
            while process.poll() is None:
                try:
                    live = psutil.Process(process.pid)
                    peak = max(peak, live.memory_info().rss + sum(child.memory_info().rss for child in live.children(recursive=True)))
                except psutil.NoSuchProcess:
                    pass
                if peak > LIMIT:
                    killed = True
                    break
                time.sleep(.5)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
        code = process.wait()
    unchanged = all(sha(path) == expected for path, expected in sources.items())
    result = {'exit_code': code, 'peak_rss_bytes': peak, 'memory_limit_terminated': killed, 'source_unchanged': unchanged,
              'production_changed': False, 'full_corpus_equivalence': False}
    with prefix.with_suffix('.receipt.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result), flush=True)
    if code or killed or not unchanged:
        raise SystemExit(code or 1)


if __name__ == '__main__':
    main()
