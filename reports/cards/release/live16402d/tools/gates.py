"""r1-cards4 / live16402d dev-root gates (same checks as r1-cards3-phase1: run_checks, run_class_v3, run_gate, run_mixed,
run_3m), plus the attachment-graph class probe. Run under one cpu_job lease of 4 on 127x04/127x08.

    python gates.py JOB REPO EVAL [step ...]      steps: smoke none class totality headline mixed stress (default all)

JOB/runtime/{r1-cards4-dev,live16402d-dev} come from assemble.py. REPO is the exported release source (probes);
EVAL is the frozen r3-compatible evaluator tree (headline/mixed; r1-cards3-phase1/repo-eval + the new pins). Each step
writes JOB/<label>.log/.exit/.json; existing labels are refused (fresh outputs only).
"""
import concurrent.futures
import fcntl
import os
from pathlib import Path
import runpy
import subprocess
import sys

job, repo, evaluator = (Path(p).resolve() for p in sys.argv[1:4])
steps = sys.argv[4:] or ['smoke', 'none', 'class', 'totality', 'headline', 'mixed', 'stress']
PY = '/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'
RT = job / 'runtime'
TOOLS = Path(__file__).resolve().parent
lock = (job / 'gates.lock').open('w')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
base_env = dict(os.environ, PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1', NUMPY_MADVISE_HUGEPAGE='0',
                OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', RAYON_NUM_THREADS='1',
                CUDA_VISIBLE_DEVICES='', NUMBA_CACHE_DIR=str(job / 'numba-cache'))
for key in ('CLASHER_ROOT', 'CLASHER_EVAL_RUNTIME_ROOT', 'CLASHER_DELAY_NATIVE_DIR'):
    base_env.pop(key, None)


def run(label, args, pin='live16402d', cwd=repo, extra=None):
    env = dict(base_env, CLASHER_BOT_RUNTIME=str(RT / (pin + '-dev')), CLASHER_BOT_RUNTIME_PINS=pin, **(extra or {}))
    with (job / (label + '.log')).open('x') as f:
        p = subprocess.run(['nice', '-n', '15', PY, '-B', *map(str, args)], cwd=cwd, env=env, stdout=f,
                           stderr=subprocess.STDOUT)
    (job / (label + '.exit')).write_text(f'{p.returncode}\n')
    print(label, 'exit', p.returncode, flush=True)
    return p.returncode


def parallel(jobs, width):
    with concurrent.futures.ThreadPoolExecutor(max_workers=width) as pool:
        codes = [f.result() for f in [pool.submit(run, *j[:2], **j[2]) for j in jobs]]
    assert all(c == 0 for c in codes), codes


PINS = ('r1-cards4', 'live16402d')
if 'smoke' in steps:
    parallel([('smoke-' + p, ['reports/cards/runtime/tools/smoke_scope.py'], dict(pin=p)) for p in PINS], 2)
if 'none' in steps:
    parallel([('none-' + p, ['reports/cards/runtime/tools/none_stats_probe.py', '--out', job / f'none-{p}.json'],
               dict(pin=p)) for p in PINS], 2)
if 'class' in steps:
    parallel([(f'objects-{i}', ['reports/cards/runtime/tools/object_templates_probe.py', '--shard', f'{i}/4', '--out',
                                job / f'objects-{i}.json'], {}) for i in range(4)], 4)
if 'totality' in steps:
    jobs = []
    for cfg in ('root', 'runtime'):
        for mode in ('plain', 'scrub'):
            args = ['reports/cards/live16402/tools/totality_live.py', '--roots',
                    '/mpac/sdicks02/jobs/clasher/cards/runtime/roots-nt', '--out', job / f'totality-{cfg}-{mode}.json']
            args += ['--runtime-config'] if cfg == 'runtime' else []
            args += ['--scrub'] if mode == 'scrub' else []
            jobs.append((f'totality-{cfg}-{mode}', args, {}))
    parallel(jobs, 4)
if 'headline' in steps:
    # Baseline arm (r1/r1-total/native-total-r1, same evaluator) is unchanged since r1-cards3: its 12 command hashes
    # are taken from reports/cards/r1-cards3/receipts/GATES.json by summarize.py, not re-run.
    assert run('headline-candidate', ['-m', 'bot.eval.headline', '--out', job / 'hl-candidate', '--candidate',
                                      'K4L-R-gs-rw-fc-p2', '--opponents', 'R3a,v1', '--games', '6', '--workers', '1'],
               pin='r1-cards4', cwd=evaluator) == 0
if 'mixed' in steps:
    parallel([('mixed', [TOOLS / 'run_mixed.py', evaluator, job / 'mixed.jsonl', 'plain'], dict(cwd=evaluator)),
              ('mixed-3m', [TOOLS / 'run_mixed.py', evaluator, job / 'mixed-3m.jsonl', '3m'], dict(cwd=evaluator))], 2)
if 'stress' in steps:
    refs = sorted(job.glob('ref_*.py'))
    assert refs, 'stress needs JOB/ref_<commit>.py reference helpers'
    args = [TOOLS / 'graph_stress.py', evaluator, job / 'stress.json', '--seeds', '6']
    for r in refs:
        args += ['--ref', f'{r.stem}={r}']
    assert run('stress', args, cwd=evaluator) == 0
print('GATES COMPLETE', steps, flush=True)
