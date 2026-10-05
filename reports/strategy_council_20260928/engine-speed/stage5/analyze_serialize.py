"""JSON-only adapter for NumPy booleans; the sealed statistical code is unchanged."""
import hashlib
import json
from pathlib import Path
import runpy
import numpy as np

HERE=Path(__file__).resolve().parent
original=json.JSONEncoder.default

def native_scalar(self,value):
    if isinstance(value,np.generic):return value.item()
    return original(self,value)

json.JSONEncoder.default=native_scalar
runpy.run_path(str(HERE/'analyze.py'),run_name='__main__')
from qualify import write
write(HERE/'analysis-serialization.json',dict(
    sealed_analysis_sha256=hashlib.sha256((HERE/'analyze.py').read_bytes()).hexdigest(),
    adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    change='JSON encoding only: NumPy scalar booleans become native Python booleans. Statistical code, draws, intervals, decisions and all sealed files are unchanged.'))
