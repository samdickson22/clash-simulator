from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path.cwd()
OUT = ROOT/'reports/strategy_council_20260928/live-loop/v4/mac-native-build48'
ES = ROOT/'reports/strategy_council_20260928/engine-speed'
env = dict(os.environ, PYTHONPATH=f'{ROOT}/engine-rs:{ROOT}/src:{ES}/stage6',
           PYTHONDONTWRITEBYTECODE='1', CLASHER_ROOT=str(ROOT), STAGE6_SUFFIX='mac-native-build48',
           OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1',
           RAYON_NUM_THREADS='1', YOLO_AUTOINSTALL='false')
def run(mode):
    started = time.time()
    cmd = [sys.executable, '-B', str(OUT/'verify_gate.py'), mode]
    with (OUT/f'{mode}.log').open('x') as log:
        child = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
        meta = dict(mode=mode, pid=child.pid, started=started, command=cmd)
        (OUT/f'{mode}.process.json').write_text(json.dumps(meta, indent=2)+'\n')
        print('START', mode, child.pid, flush=True)
        code = child.wait()
    meta.update(exit_code=code, ended=time.time(), wall_seconds=time.time()-started)
    (OUT/f'{mode}.exit.json').write_text(json.dumps(meta, indent=2)+'\n')
    print('END', mode, code, round(meta['wall_seconds'], 2), flush=True)
    return meta

tasks = ['runtime', 'stage5', 'stage6', 'p16', 'c56', 'random'] + [f'recorded-{i}' for i in range(8)]
results = []
with ThreadPoolExecutor(max_workers=2) as pool:
    for job in as_completed([pool.submit(run, x) for x in tasks]):
        results.append(job.result())
        (OUT/'verification-progress.json').write_text(json.dumps(results, indent=2)+'\n')
assert all(r['exit_code'] == 0 for r in results), 'One or more checks failed; all logs preserved'
sys.path[:0] = [str(ROOT/'engine-rs'), str(ROOT/'src'), str(ES)]
import broad_identity
rows = [json.loads((ES/f'stage6/recorded-mac-native-build48-game{i}.json').read_text()) for i in range(8)]
prov = broad_identity.provenance()
assert all(r['provenance'] == prov and r['ok'] for r in rows)
merged = dict(suite='recorded', count=8, provenance=prov, results={str(r['index']):r['row'] for r in rows}, mismatches=[])
(OUT/'recorded.json').write_text(json.dumps(merged, indent=2)+'\n')
cmd = [sys.executable, '-B', str(ES/'broad_identity.py'), 'recorded', 'check', str(ES/'recorded_identity_baseline_admitted.json'), '--output', str(OUT/'recorded.json')]
with (OUT/'recorded-final-check.log').open('x') as log:
    subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
(OUT/'verification-complete.json').write_text(json.dumps(dict(passed=True, results=results), indent=2)+'\n')
print('ALL VERIFICATION PASSED', flush=True)
