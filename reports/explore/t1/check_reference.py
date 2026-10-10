"""Re-run reviewed E4 pooling, compare sealed outputs, emit health-only evidence."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from common import sha, utc
from release_reference import POOL_FILES, beneath, pool_inputs, require


def pool_command(measurement_root, descriptor, target):
    # -I omits the script directory too: admit only this explicitly pinned root.
    bootstrap = ('import runpy,sys;root=sys.argv.pop(1);script=sys.argv.pop(1);'
                 'sys.path.insert(0,root);sys.argv[0]=script;runpy.run_path(script,run_name="__main__")')
    return [sys.executable, '-I', '-c', bootstrap, str(measurement_root),
            str(measurement_root / 'measure_tiers.py'), '--pool-fleet-references',
            '--pool-input', str(descriptor), '--pool-input-sha256', sha(descriptor), '--output', str(target)]


def check(descriptor, pool, measurement_root, output):
    descriptor, pool, measurement_root = map(lambda p: Path(p).resolve(), (descriptor, pool, measurement_root))
    output = Path(output)
    require(not output.exists(), 'Pool check receipt already exists')
    manifest = json.loads((pool / 'receipt-manifest.json').read_text())
    seal_sha = sha(pool / 'receipt-manifest.json')
    require(manifest['scope'] == 'FLEET-POOL' and manifest['status'] == 'complete'
            and POOL_FILES <= set(manifest['files']), 'Incomplete production pool')
    for name, digest in manifest['files'].items():
        path = (pool / name).resolve()
        require(beneath(path, pool) and sha(path) == digest, 'Pooled artifact changed')
    before = pool_inputs(descriptor, measurement_root)
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               PYTHONDONTWRITEBYTECODE='1')
    # This mode performs read-only pooling, not a fleet or Mac measurement.
    # Its normal stdout is suppressed; only check health is emitted below.
    # Preserve failure.json and stderr privately even after scratch is removed.
    diagnostics = output.with_name(output.name + '.diagnostics')
    diagnostics.mkdir(parents=True, mode=0o700, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='t1-pool-recheck-', dir='/mpac/sdicks02/tmp') as scratch:
        target = Path(scratch) / 'pool'
        try:
            with (diagnostics / 'stderr.txt').open('x') as stderr:
                subprocess.run(pool_command(measurement_root, descriptor, target), env=env,
                               stdout=subprocess.DEVNULL, stderr=stderr, check=True)
            repeated = json.loads((target / 'receipt-manifest.json').read_text())
            require(repeated['scope'] == 'FLEET-POOL' and repeated['status'] == 'complete'
                    and repeated['files'] == manifest['files'], 'E4 pooled outputs differ on recheck')
            for name, digest in manifest['files'].items():
                require(sha(target / name) == digest, 'Rechecked pooled bytes differ')
        except Exception as error:
            import shutil
            if (target / 'failure.json').is_file():
                shutil.copyfile(target / 'failure.json', diagnostics / 'e4-failure.json')
            (diagnostics / 'failure-health.json').write_text(json.dumps(dict(
                passes=False, outcome_access=False, error_type=type(error).__name__,
                returncode=getattr(error, 'returncode', None), checked_at_utc=utc())) + '\n')
            raise
    require(pool_inputs(descriptor, measurement_root) == before, 'Reference inputs changed during recheck')
    require(sha(pool / 'receipt-manifest.json') == seal_sha, 'Pool seal changed during recheck')
    for name, digest in manifest['files'].items():
        require(sha(pool / name) == digest, 'Pooled output changed during recheck')
    result = dict(schema='clasher.t1.pool-check.v1', passes=True, checked_at_utc=utc(), outcome_access=False,
                  pool_manifest_sha256=seal_sha, descriptor_sha256=sha(descriptor),
                  checker_sha256=sha(__file__), output_files=manifest['files'], input_files=before)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('descriptor', 'pool', 'measurement-root', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    result = check(a.descriptor, a.pool, a.measurement_root, a.output)
    print(json.dumps(dict(passes=True, checked_inputs=len(result['input_files']), receipt_sha256=sha(a.output))))


if __name__ == '__main__':
    main()
