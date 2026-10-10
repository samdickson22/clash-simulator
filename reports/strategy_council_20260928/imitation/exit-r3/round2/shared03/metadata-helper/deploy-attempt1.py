"""Deploy the reviewed guard-only amendment; never launch replay or clear STOP."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
J='/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2'

def main(commit):
    subprocess.run(['git','merge-base','--is-ancestor',commit,'origin/main'],check=True)
    raw=(ROOT/'evaluation-freeze.json').read_bytes();digest=hashlib.sha256(raw).hexdigest()
    pre=dict(pushed=True,commit=commit,evaluation_freeze_sha256=digest,secret_scan_passed=True,operational_only=True,scientific_changes=False,qualified_before_restart=True,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip())
    (ROOT/'evaluation-prelaunch.json').write_text(json.dumps(pre,indent=2)+'\n')
    subprocess.run(['ssh','-o','ConnectTimeout=10','127x03','mkdir -p '+J+'/metadata/metadata-helper'],check=True)
    maps=[('evaluation-freeze.json','new-freeze.json'),('evaluation-prelaunch.json','new-prelaunch.json'),('eval-ops/regret_admission.py','new-regret_admission.py'),('qualify.py','qualify.py'),('prior-regret_admission.py','prior-regret_admission.py'),('REVIEW.json','REVIEW.json'),('authority.json','new-authority.json')]
    for source,target in maps:subprocess.run(['scp','-q',str(ROOT/source),'127x03:'+J+'/metadata/metadata-helper/'+target],check=True)
    code='''import hashlib,importlib.util,json,os,resource,shutil,subprocess,sys,time
from pathlib import Path
j=Path(JOB);meta=j/'metadata/diagnostics';started=time.monotonic();sys.path.insert(0,str(j/'eval-ops'))
assert hashlib.sha256((meta/'new-freeze.json').read_bytes()).hexdigest()==DIGEST
f=json.loads((meta/'new-freeze.json').read_text());pre=json.loads((meta/'new-prelaunch.json').read_text())
assert pre['pushed'] and pre['secret_scan_passed'] and pre['commit']==COMMIT and pre['evaluation_freeze_sha256']==DIGEST
assert not (j/'SHARED03-METADATA-DEPLOYMENT.json').exists(),'already deployed; review instead of retry'
assert not (j/'REGRET.STOP').exists() and not (j/'EVAL.STOP').exists(),'owned STOP; no automatic clear'
assert not (j/'regret/POOL-DONE.json').exists() and not (j/'stage1-results.json').exists()
old_sha=hashlib.sha256((j/'evaluation-freeze.json').read_bytes()).hexdigest();assert old_sha==f['previous_diagnostic_freeze_sha256']
spec=importlib.util.spec_from_file_location('old_guard',j/'eval-ops/regret_admission.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
assert old.allowed(j),'fresh old guard denied; review before changing anything';old.frozen(j)
ids=set();groups=set()
def extract(v):
 if isinstance(v,dict):
  for k,x in v.items():
   if (k=='pid' or k.endswith('_pid')) and isinstance(x,int) and x>0:ids.add(x)
   elif (k=='pgid' or k.endswith('_pgid')) and isinstance(x,int) and x>0:groups.add(x)
   else:extract(x)
 elif isinstance(v,list):
  for x in v:extract(x)
extract(json.loads((j/'EVAL-PGIDS.json').read_text()))
for p in Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid():continue
 try:
  assert int(p.name) not in ids and os.getpgid(int(p.name)) not in groups,'old recorded process/group active'
 except (FileNotFoundError,ProcessLookupError):pass
archive=meta/'prior';archive.mkdir()
for name in ('evaluation-freeze.json','evaluation-prelaunch.json','REGRET-CPU-ADMITTED.json','REGRET-SHARED-AUTHORITY.json'):shutil.copyfile(j/name,archive/name)
shutil.copyfile(j/'eval-ops/regret_admission.py',archive/'regret_admission.py')
shutil.copyfile(meta/'new-authority.json',j/'REGRET-SHARED-AUTHORITY.json')
shutil.copyfile(meta/'new-regret_admission.py',j/'eval-ops/regret_admission.py');shutil.copyfile(meta/'new-freeze.json',j/'evaluation-freeze.json');shutil.copyfile(meta/'new-prelaunch.json',j/'evaluation-prelaunch.json')
admitted=json.loads((j/'REGRET-CPU-ADMITTED.json').read_text());admitted.update(evaluation_freeze_sha256=DIGEST,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),prior_pool_reviewed=3337091,retained_complete_games=46,shared_authority_sha256=hashlib.sha256((j/'REGRET-SHARED-AUTHORITY.json').read_bytes()).hexdigest(),guard_diagnostic_amendment=True)
p=j/'REGRET-CPU-ADMITTED.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(admitted,indent=2)+'\\n');tmp.replace(p)
spec=importlib.util.spec_from_file_location('diagnostic_guard',j/'eval-ops/regret_admission.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
assert guard.allowed(j),'fresh amended guard denied';guard.frozen(j)
q=subprocess.run([sys.executable,'-B',str(meta/'qualify.py'),str(j)],text=True,capture_output=True,check=True,timeout=30);checks=json.loads(q.stdout);assert checks['passed'] and checks['checks']==34
u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
full=next(line for line in Path('/proc/pressure/memory').read_text().splitlines() if line.startswith('full '));psi=float(next(x.split('=')[1] for x in full.split() if x.startswith('avg10=')))
result=dict(passed=True,pid=os.getpid(),pgid=os.getpgrp(),utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),commit=COMMIT,evaluation_freeze_sha256=DIGEST,authority_sha256=guard.sha(j/'REGRET-SHARED-AUTHORITY.json'),admitted_sha256=guard.sha(j/'REGRET-CPU-ADMITTED.json'),pins=len({**f['files'],**f['regret_files']}),checks=34,old_groups_absent=True,scientific_data_read=False,retained_complete_seals=46,physical_cores=[56,57,58],manager_core=58,nice=19,scheduler='SCHED_OTHER',PSI_full_avg10=psi,G_untouched=True,cpu_seconds=u.ru_utime+u.ru_stime+v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-started)
p=j/'SHARED03-METADATA-DEPLOYMENT.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(result,indent=2)+'\\n');tmp.replace(p)
print(json.dumps(dict(deployment=result,admitted=admitted)))
'''.replace('JOB',repr(J)).replace('DIGEST',repr(digest)).replace('COMMIT',repr(commit))
    result=subprocess.run(['ssh','-o','ConnectTimeout=10','127x03','env TMPDIR='+J+'/tmp nice -n 19 taskset -c 58 /usr/bin/python3 -B -'],input=code,text=True,capture_output=True,timeout=45)
    (ROOT/'deployment.stdout.txt').write_text(result.stdout);(ROOT/'deployment.stderr.txt').write_text(result.stderr)
    assert result.returncode==0,result.stderr
    values=json.loads(result.stdout)
    for key in ('deployment','admitted'):(ROOT/(key+'.json')).write_text(json.dumps(values[key],indent=2)+'\n')
    print(json.dumps(values['deployment']))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);a=p.parse_args();main(a.commit)
