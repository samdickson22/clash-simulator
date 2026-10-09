"""Complete pre-fit checks after the detached store copy/verification."""
import os
from pathlib import Path
import socket
import subprocess
import time
p=Path('/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1')
gpu=('/mpac/sdicks02/repos/clasher-lease/envs/clasher-gpu/bin/python'
     if socket.gethostname().split('.')[0]=='127x09' else '/mpac/sdicks02/envs/clasher-gpu/bin/python')
deadline=time.monotonic()+1800
while not (p/'venv/bin/python').exists():
    if time.monotonic()>deadline:raise TimeoutError('task venv unavailable')
    time.sleep(2)
time.sleep(2)
base=subprocess.check_output([gpu,'-c','import sysconfig;print(sysconfig.get_path("purelib"))'],text=True).strip()
target=subprocess.check_output([str(p/'venv/bin/python'),'-c','import sysconfig;print(sysconfig.get_path("purelib"))'],text=True).strip()
(Path(target)/'qualified-gpu.pth').write_text(base+'\n')
while not (p/'inputs/human-verified.json').exists():
    if time.monotonic()>deadline:raise TimeoutError('human SHA verification unavailable')
    time.sleep(5)
env=dict(os.environ,PYTHONPATH=str(p/'source')+':'+str(p/'source/src'),
    PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
subprocess.run([str(p/'venv/bin/python'),'-B',str(p/'ops/check_ready.py'),str(p)],check=True,env=env)
