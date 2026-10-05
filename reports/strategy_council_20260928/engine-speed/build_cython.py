"""Build an opt-in source snapshot outside the checkout. Run with Cython's Python.

Usage: nice -n 10 ~/.cache/clasher-engine-speed/cp312cy/bin/python build_cython.py
Then prefix a command with PYTHONPATH=~/.cache/clasher-engine-speed/stage0-cython/src.
The normal source import path is unchanged. A manifest pins the source hashes.
"""
from __future__ import annotations
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULES = (
    'kinematics', 'native_tilemap', 'arena', 'unit_traits', 'native_spatial',
    'pathfinding', 'placement', 'battle', 'entities',
    'rl/public_observation', 'rl/structured_obs', 'rl/action_space',
)


def main():
    import Cython
    import setuptools
    out = Path.home() / '.cache/clasher-engine-speed/stage0-cython'
    if out.exists():
        raise FileExistsError(f'{out}: preserve existing build; choose a fresh destination')
    source = ROOT / 'src/clasher'
    dest = out / 'src/clasher'
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns('__pycache__', '*.so', '*.pyc'))
    manifest = {'python': sys.version, 'cython': Cython.__version__, 'setuptools': setuptools.__version__,
                'compiler_directives': {'binding': True, 'annotation_typing': False},
                'source_sha256': {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(source.rglob('*.py'))}}
    # Numba requires a Python function. Relocate this unchanged function only in
    # the build snapshot; the repository engine and its default imports stay intact.
    battle = dest / 'battle.py'
    text = battle.read_text()
    start = text.index('if njit is not None:\n')
    end = text.index('\n\n@dataclass\nclass BattleState:', start)
    helper = 'import numpy as np\ntry:\n    from numba import njit\nexcept Exception:\n    njit = None\n\n' + text[start:end] + '\n'
    (dest / '_cython_numba_helper.py').write_text(helper)
    text = text[:start] + 'if njit is not None:\n    from ._cython_numba_helper import _build_blocked_mask_numba\n' + text[end:]
    battle.write_text(text)
    manifest['build_only_transform'] = 'battle.py numba function moved verbatim to uncompiled _cython_numba_helper.py'
    out.mkdir(exist_ok=True)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    # Python annotations allow subclasses such as defaultdict. Cython's exact
    # builtin inference does not, so retain Python semantics for annotations.
    # -j 1 includes C compilation; never fan out onto the occupied host cores.
    subprocess.run([sys.executable, '-m', 'Cython.Build.Cythonize', '-i', '-3', '-j', '1',
                    '-X', 'binding=True', '-X', 'annotation_typing=False',
                    *[str(dest / f'{name}.py') for name in MODULES]],
                   cwd=out, check=True)
    print(json.dumps({'import_root': str(out / 'src'), 'modules': MODULES}), flush=True)


if __name__ == '__main__':
    main()
