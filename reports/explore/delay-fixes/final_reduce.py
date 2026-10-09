"""Run final paired reduction on home 08 at idle priority, with GPU core exclusion."""
import importlib.util
import multiprocessing
from pathlib import Path
import runpy
import subprocess
import sys

from clasher.analysis.loss_review.delay_runtime import GPUWatch


root = Path(__file__).resolve().parent


def reduce_work():
    subprocess.run([sys.executable, '-m', 'pytest', '-q',
                    'tests/analysis/test_loss_review.py',
                    'tests/analysis/test_delay_fixes.py',
                    'tests/analysis/test_throughput_guard.py',
                    'tests/analysis/test_delay_fixes_summary.py'],
                   cwd=root.parents[2], check=True)
    for script, arguments in [
        ('summarize.py', ['--source', str(root / 'shards'), '--out', str(root / 'results.json'),
                          '--expected-pairs', '1250', '--bootstrap', '5000',
                          '--controls-source', str(root / 'lag-only/shards'), '--allow-partial-controls']),
        ('audit_compute.py', ['--root', str(root), '--out', str(root / 'compute-audit.json')]),
    ]:
        sys.argv = [script, *arguments]
        runpy.run_path(str(root / script), run_name='__main__')
    if importlib.util.find_spec('matplotlib'):
        sys.argv = ['plot_results.py', '--root', str(root)]
        runpy.run_path(str(root / 'plot_results.py'), run_name='__main__')
    else:
        print('Plot requires the isolated task plotting environment.', flush=True)
    (root / 'reduction-complete.json').write_text('{"original_paired_seeds":1250,"status":"reduction completed; control counts in results.json"}\n')


if __name__ == '__main__':
    guard = GPUWatch(root / 'reduction-gpu.jsonl', True, config_path=root / 'guard-config.json')
    guard.prepare()
    child = multiprocessing.Process(target=reduce_work)
    child.start()
    with guard:
        child.join()
    if child.exitcode:
        raise SystemExit(child.exitcode)
