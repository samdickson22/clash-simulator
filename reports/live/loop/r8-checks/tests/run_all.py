"""Portable, offline only. Requires Python>=3.10 and numpy. No model/Runtime/host imports."""
from pathlib import Path
import argparse,subprocess,sys,os,json,datetime,tempfile,hashlib
p=argparse.ArgumentParser();p.add_argument('--output',type=Path);a=p.parse_args()
P=Path(__file__).resolve().parents[1];out=a.output or Path(tempfile.mkdtemp(prefix='r8-canonical-tests-'))
out.mkdir(parents=True,exist_ok=True)
env={**os.environ,'R8_TEST_OUT':str(out.resolve()),'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'}
def verify_sources():
 for row in json.loads((P/'MANIFEST.json').read_text())['payloads']:
  assert hashlib.sha256((P/row['candidate']).read_bytes()).hexdigest()==row['candidate_sha256'],row['path']
  if row['base']:assert hashlib.sha256((P/row['base']).read_bytes()).hexdigest()==row['base_sha256'],row['path']
verify_sources()
commands=[]
for name in['combined_test.py','producer_test.py','freshness_test.py']:
 path=P/'tests'/name;argv=['nice','-n19',sys.executable,'-B',str(path)];record={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'argv':argv,'test_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'env':{k:env[k]for k in['R8_TEST_OUT','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','PYTHONDONTWRITEBYTECODE']}}
 with(out/(name+'.log')).open('w')as f:r=subprocess.run(argv,env=env,stdout=f,stderr=subprocess.STDOUT)
 record['exit']=r.returncode;commands.append(record);(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 print(name,r.returncode,flush=True)
 if r.returncode:print((out/(name+'.log')).read_text());raise SystemExit(r.returncode)
verify_sources()
print('PASS portable canonical checks:',out)
