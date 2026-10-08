"""Use only this study's pinned runtime, on either platform."""
import os
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNTIME = HERE / 'runtime'
os.environ['CLASHER_ROOT'] = str(RUNTIME)
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'RAYON_NUM_THREADS'):
    os.environ[key] = '1'
sys.dont_write_bytecode = True
sys.path[:0] = [str(RUNTIME / 'support'), str(RUNTIME / 'engine-rs'), str(RUNTIME / 'src'), str(RUNTIME / 'reports/strategy_council_20260928/engine-speed')]
