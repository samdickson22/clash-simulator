"""Verify the unadmitted package and run its sole permitted no-fit proof."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(manifest):
    root = Path(manifest['source_root'])
    current = {str(path.relative_to(root)) for path in (root/'src/clasher').rglob('*.py')}
    expected = {name for name in manifest['source_files'] if name.startswith('src/clasher/')}
    if current != expected:
        raise RuntimeError('source file inventory changed; create a new staging revision')
    for name, digest in manifest['source_files'].items():
        if sha(root/name) != digest:
            raise RuntimeError(f'source pin changed: {name}')
    for name, digest in manifest['package_files'].items():
        if sha(PACKAGE/name) != digest:
            raise RuntimeError(f'package pin changed: {name}')
    if sha(root/'gamedata.json') != manifest['unchanged_workspace_data_sha256']:
        raise RuntimeError('workspace default changed since staging; review provenance')


def main():
    if sys.argv[1:] not in ([], ['--verify-only']):
        raise SystemExit('Only the no-fit proof and --verify-only are supported; this package is unadmitted.')
    manifest = json.loads((PACKAGE/'manifest.json').read_text())
    verify(manifest)
    if sys.argv[1:]:
        print('Unadmitted package pins verified; no execution authorized.')
        return
    runtime = PACKAGE/'runtime'
    for name in ('tmp','cache','numba','matplotlib','torch','pycache'):
        (runtime/name).mkdir(parents=True,exist_ok=True)
    environment = os.environ.copy()
    environment.update({
        'CLASHER_ROOT':str(PACKAGE/'inputs'),
        'PYTHONPATH':str(Path(manifest['source_root'])/'src'),
        'PYTHONDONTWRITEBYTECODE':'1',
        'PYTHONPYCACHEPREFIX':str(runtime/'pycache'),
        'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1',
        'TMPDIR':str(runtime/'tmp'),'XDG_CACHE_HOME':str(runtime/'cache'),
        'NUMBA_CACHE_DIR':str(runtime/'numba'),'MPLCONFIGDIR':str(runtime/'matplotlib'),
        'TORCH_HOME':str(runtime/'torch'),
    })
    result = subprocess.run([manifest['python_executable'],'-B',str(PACKAGE/'proof.py')],
        cwd=PACKAGE/'inputs',env=environment,text=True,capture_output=True)
    (runtime/'proof.stdout.log').write_text(result.stdout)
    (runtime/'proof.stderr.log').write_text(result.stderr)
    verify(manifest)
    if result.returncode:
        raise SystemExit(f'No-fit proof failed ({result.returncode}); inspect runtime/proof.stderr.log')
    print(result.stdout,end='')
    print('Source and package pins unchanged after proof. Status: UNADMITTED STAGING.')


if __name__ == '__main__':
    main()
