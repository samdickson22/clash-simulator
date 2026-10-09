"""Use independent unselected horizon arms while tuning weights separately."""
import json,subprocess,shlex,time
from pathlib import Path
root=Path(__file__).resolve().parents[3];r=root/'reports/explore/tempo';target='/mpac/sdicks02/repos/clasher-lease/tempo-runtime';records=[]
for host,offset,workers in [('127x09',100,20),('127x13',150,20),('127x14',200,20),('127x15',250,20),('127x16',300,40)]:
 def read(path):return subprocess.run(['ssh','-o','BatchMode=yes',host,'nice -n 10 chrt --idle 0 cat '+shlex.quote(path)],text=True,capture_output=True)
 if host=='127x16':
  result=read('/mpac/sdicks02/repos/clasher-lease/delay-fixes-runtime/reports/explore/delay-fixes/guard-config.json');job=json.loads(result.stdout)['jobs'][0]
  guard=['--gpu-guard','--throughput-log',job['log_path'],'--throughput-field',job['field'],'--baseline-rate',str(job['baseline']),'--gpu-pid',str(job['pid'])]
 else:
  result=read(target+'/reports/explore/tempo/receipts/perception-rate.baseline.json')
  if result.returncode:records.append(dict(host=host,event='no throughput baseline',stdout=result.stdout,stderr=result.stderr));continue
  job=json.loads(result.stdout);guard=['--gpu-guard','--throughput-log',job['log_path'],'--throughput-field',job['field'],'--baseline-rate',str(job['baseline'])]
 label=f'tempo-early-{host}-v1'
 command=['bash','/mpac/sdicks02/repos/clasher-lease/run_v2.sh','--max-processes',str(workers+4),'--expected-pss-gb',str(round(workers*.7+2,1)),label,'--','nice','-n','10','chrt','--idle','0','taskset','-c',f'64-{63+workers}','env',f'CLASHER_ROOT={target}',f'PYTHONPATH={target}/src:{target}/engine-rs','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1','RAYON_NUM_THREADS=1','/mpac/sdicks02/repos/clasher-lease/repo/.venv/bin/python','-B',target+'/reports/explore/tempo/worker_runtime.py','--offset',str(offset),'--pairs','50','--workers',str(workers),'--arms','0','H12','H16','--out',target+'/reports/explore/tempo/early-reporting','--max-seconds','840','--case-costs',target+'/reports/explore/tempo/case-costs.json',*guard]
 result=subprocess.run(['ssh','-o','BatchMode=yes',host,shlex.join(['nice','-n','10','chrt','--idle','0',*command])],text=True,capture_output=True,timeout=90);records.append(dict(host=host,label=label,offset=offset,pairs=50,workers=workers,status=result.returncode,stdout=result.stdout,stderr=result.stderr,command=command,utc=time.time()))
 print(json.dumps(records[-1]),flush=True)
(r/'receipts/early-leases-launch.json').write_text(json.dumps(records,indent=2)+'\n')
