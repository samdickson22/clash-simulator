"""Measure cold versus warmed source/dependency startup under an external cache."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[3];out=root/'reports/explore/search-ab/receipts';prefix=root/'reports/explore/search-ab/startup-cache-v2';env=dict(os.environ,PYTHONPYCACHEPREFIX=str(prefix));env.pop('PYTHONDONTWRITEBYTECODE',None)
code='from clasher.analysis.loss_review import simulate; simulate.OPTIONS={}; simulate.initialize()'
source=root/'src/clasher/analysis/loss_review/simulate.py';before=hashlib.sha256(source.read_bytes()).hexdigest();times=[]
for warm in (False,True):
    if warm:
        subprocess.run([sys.executable,'-m','compileall','-q',str(root/'src/clasher/analysis/loss_review'),str(root/'reports/explore/search-ab'),str(root/'engine-rs')],env=env,check=True)
        subprocess.run([sys.executable,'-c',code],env=env,check=True)
    start=time.perf_counter();subprocess.run([sys.executable,'-B','-c',code],env=env,check=True);times.append(time.perf_counter()-start)
assert hashlib.sha256(source.read_bytes()).hexdigest()==before
result=dict(cold_seconds=times[0],warm_seconds=times[1],ratio=times[1]/times[0],bytecode_prefix=str(prefix),source_sha256_unchanged=before,scope='simulate.initialize; Resources + torch + public reconstruction imports; one idle CPU')
(out/'startup-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
