import os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RUNTIME=HERE/'runtime'
os.environ['CLASHER_ROOT']=str(RUNTIME)
os.environ['PYTHONDONTWRITEBYTECODE']='1'
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[k]='1'
sys.dont_write_bytecode=True
sys.path[:0]=[str(RUNTIME/'support'),str(RUNTIME/'engine-rs'),str(RUNTIME/'src'),str(RUNTIME/'reports/strategy_council_20260928/engine-speed')]
