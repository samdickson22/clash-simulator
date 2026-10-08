import hashlib
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

def run(label, cmd):
    started = time.time()
    with (OUT/f'{label}.log').open('x') as log:
        child = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
        print('START', label, child.pid, flush=True)
        code = child.wait()
    meta = dict(command=cmd, pid=child.pid, exit_code=code, started=started, ended=time.time(), wall_seconds=time.time()-started)
    (OUT/f'{label}.exit.json').write_text(json.dumps(meta, indent=2)+'\n')
    print('END', label, code, round(meta['wall_seconds'], 2), flush=True)
    assert code == 0, (label, code)
    return meta

def main():
    # Wait only for this task's known supervisor, with a finite two-hour bound.
    for _ in range(720):
        p = subprocess.run(['ps', '-p', '94993', '-o', 'command='], capture_output=True, text=True)
        if p.returncode or 'mac-native-build48/verify_all.py' not in p.stdout:
            break
        time.sleep(10)
    else:
        raise TimeoutError('Verification supervisor still active after two hours')
    results = json.loads((OUT/'verification-progress.json').read_text())
    assert len(results) == 14
    assert all(r['exit_code'] == 0 for r in results if r['mode'] != 'runtime'), results
    retry = run('runtime-retry', [sys.executable, '-B', str(OUT/'verify_gate.py'), 'runtime'])
    sys.path[:0] = [str(ROOT/'engine-rs'), str(ROOT/'src'), str(ES)]
    import broad_identity
    rows = [json.loads((ES/f'stage6/recorded-mac-native-build48-game{i}.json').read_text()) for i in range(8)]
    prov = broad_identity.provenance()
    assert all(r['provenance'] == prov and r['ok'] for r in rows)
    merged = dict(suite='recorded', count=8, provenance=prov, results={str(r['index']):r['row'] for r in rows}, mismatches=[])
    (OUT/'recorded.json').write_text(json.dumps(merged, indent=2)+'\n')
    run('recorded-final-check', [sys.executable, '-B', str(ES/'broad_identity.py'), 'recorded', 'check', str(ES/'recorded_identity_baseline_admitted.json'), '--output', str(OUT/'recorded.json')])
    (OUT/'verification-complete.json').write_text(json.dumps(dict(passed=True, results=results, runtime_retry=retry, initial_runtime_wrapper_attempt_excluded=True), indent=2)+'\n')
    run('latency-smoke', [sys.executable, '-B', str(OUT.parent/'latency_suite.py'),
        '--data', str(ROOT/'runtime-data'), '--matches', str(ROOT/'runtime-data/matches'),
        '--device', 'mps', '--minimum-matches', '1', '--minimum-taps', '50', '--maximum-matches', '4',
        '--output', str(OUT/'latency-smoke')])
    run('latency-report', [sys.executable, '-B', str(OUT.parent/'latency_report.py'), str(OUT/'latency-smoke'), str(OUT/'latency-smoke.json')])
    print('POST CHECKS COMPLETE', flush=True)

if __name__ == '__main__':
    main()
