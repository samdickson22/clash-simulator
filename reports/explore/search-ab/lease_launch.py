"""Bounded short-shard scheduler, using only v2 admission and lease-local paths."""
import datetime,json,subprocess,time,sys,shlex
from pathlib import Path
from clasher.analysis.loss_review.scheduling import lane_failed
root=Path(__file__).resolve().parent
hosts=['127x04','127x08','127x09','127x14','127x16'] # Current coordinator authorization; 03/11/13/15 remain excluded.
remote='/mpac/sdicks02/repos/clasher-lease/search-ab-runtime-v2'
manifest=json.loads((root/'shards.json').read_text());queue=sorted(manifest['shards'],key=lambda s:(s['retained_home_games'],s['offset']))
active={};attempts={};completed=[];disabled=[];records=[];began=time.monotonic();lane_failures={}
throughput_config=json.loads(Path(sys.argv[sys.argv.index('--throughput-config')+1]).read_text()) if '--throughput-config' in sys.argv else {}
if '--resume-state' in sys.argv:
 prior=json.loads((root/'receipts/lease-scheduler.json').read_text())
 active=prior['active'];queue=prior['queue'];completed=prior['completed'];disabled=prior['disabled'];records=prior['records']
 for r in records:
  if 'label' in r:
   name=r['label'].split('-')[-2];attempt=int(r['label'].split('-')[-1][1:]);attempts[name]=max(attempts.get(name,0),attempt)
if '--hotfix-resume' in sys.argv:
 disabled=[h for h in disabled if h not in ('127x13','127x16')]
 records.append(dict(event='coordinator hotfix resume',utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
if '--vacate1315' in sys.argv:
 for h in ('127x13','127x15'):
  if h not in disabled:disabled.append(h)
 records.append(dict(event='coordinator vacate 13/15; active shards drain under original 14-minute deadline',utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
if '--block14' in sys.argv and '127x14' not in disabled:disabled.append('127x14')
if '--block11' in sys.argv and '127x11' not in disabled:disabled.append('127x11')

def run(args,**kwargs):
 if args[0]=='ssh' and '127x04' in args:args=['bash','-c',args[-1]]
 return subprocess.run(args,text=True,capture_output=True,timeout=90,**kwargs)
def clasher_count():
 count=0
 for p in Path('/proc').glob('[0-9]*/cmdline'):
  try:args=p.read_bytes().decode(errors='ignore')
  except (FileNotFoundError,PermissionError,ProcessLookupError):continue
  count+=('/mpac/sdicks02/repos/clasher' in args or 'clasher.analysis.loss_review.simulate' in args)
 return count

def save():
 (root/'receipts').mkdir(exist_ok=True)
 path=root/'receipts/lease-scheduler.json';tmp=path.with_suffix('.tmp')
 tmp.write_text(json.dumps(dict(active=active,queue=queue,completed=completed,disabled=disabled,records=records),indent=2)+'\n');tmp.replace(path)

if '--resume-idle11' in sys.argv and '127x11' in disabled:
 check=run(['ssh','-o','BatchMode=yes','127x11','nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits'])
 if check.returncode==0 and int(check.stdout.splitlines()[0])<=1024:
  disabled.remove('127x11');records.append(dict(host='127x11',event='GPU job released memory; coordinator hotfix admission resumes',utc=time.time()))

while queue or active:
 now=datetime.datetime.now(datetime.timezone.utc)
 if now>=datetime.datetime(2026,10,9,4,15,tzinfo=datetime.timezone.utc) or time.monotonic()-began>7200:break
 for host in hosts:
  if host in active:
   task=active[host];label=task['label']
   jobfile=f'/mpac/sdicks02/jobs/clasher/{label}.exit' if host in ('127x03','127x04','127x08') else f'/mpac/sdicks02/repos/clasher-lease/jobs/{label}.exit.json'
   status=run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,f'cat {jobfile} 2>/dev/null'])
   if status.returncode==0:
    record=dict(host=host,label=label,offset=task['offset'],exit=json.loads(status.stdout));records.append(record)
    target=('/mpac/sdicks02/repos/clasher/reports/explore/search-ab/runtime-v2' if host in ('127x03','127x08') else '/mpac/sdicks02/repos/clasher') if host in ('127x03','127x04','127x08') else remote
    dest=root/'shards'/task['name']
    fetch=run(['true']) if host=='127x04' else run(['rsync','-ac',f'{host}:{target}/reports/explore/search-ab/shards/{task["name"]}/',str(dest)+'/'])
    if fetch.returncode:raise RuntimeError(fetch.stderr)
    receipt=dest/'receipt.json'
    if receipt.exists() and json.loads(receipt.read_text())['games']==task['requested_games']:
     completed.append(task);lane_failures[host]=0
    else:
     queue.insert(0,{k:v for k,v in task.items() if k not in ('host','label','workers')})
     exit_record=record['exit'];code=exit_record.get('exit_code') if isinstance(exit_record,dict) else exit_record
     if code!=75:
      if lane_failed(lane_failures,host) and host not in disabled:disabled.append(host)
    del active[host]
   else:continue
  if host in disabled or not queue:continue
  if host=='127x03':
   reservation=run(['ssh','-o','BatchMode=yes',host,'test ! -e /mpac/sdicks02/jobs/clasher/GATES-03-RESERVED'])
   if reservation.returncode:
    disabled.append(host);records.append(dict(host=host,event='03 reserved; no further launches'));save();continue
  target=('/mpac/sdicks02/repos/clasher/reports/explore/search-ab/runtime-v2' if host in ('127x03','127x08') else '/mpac/sdicks02/repos/clasher') if host in ('127x03','127x04','127x08') else remote
  if host=='127x04' and clasher_count()+44>90:continue
  job=throughput_config.get(host)
  if not job:
   records.append(dict(host=host,event='no measured throughput baseline; lane not launched'))
   if host not in disabled:disabled.append(host)
   save();continue
  queue.sort(key=lambda s:-float(s.get('estimated_seconds',s['requested_games']-s['retained_home_games'])))
  task=queue.pop(0);name=task['name'];attempts[name]=attempts.get(name,0)+1
  mkdir=run(['ssh','-o','BatchMode=yes',host,f'mkdir -p {target}/reports/explore/search-ab/shards'])
  if mkdir.returncode:raise RuntimeError(mkdir.stderr)
  stage=run(['true']) if host=='127x04' else run(['rsync','-ac',str(root/'shards'/name)+'/',f'{host}:{target}/reports/explore/search-ab/shards/{name}/'])
  if stage.returncode:raise RuntimeError(stage.stderr)
  label=f'cpu-search-ab-{name}-r{attempts[name]}'
  workers=18 if host in ('127x09','127x14','127x15') else 15 if host=='127x13' else 36
  cmd=f'bash /mpac/sdicks02/repos/clasher-lease/run_v2.sh --max-processes {workers+4} --expected-pss-gb {round(workers*2/3,1)} {label} -- nice -n 9 taskset -c 64-{64+workers-1} env CLASHER_ROOT={remote} PYTHONPATH={remote}/src:{remote}/engine-rs /mpac/sdicks02/repos/clasher-lease/repo/.venv/bin/python -B {remote}/reports/explore/search-ab/lease_worker.py --offset {task["offset"]} --workers {workers}'
  if host=='127x03':
   workers=80
   cmd=f'test ! -e /mpac/sdicks02/jobs/clasher/GATES-03-RESERVED && bash /mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/fleet/fleet_run.sh {label} taskset -c 0-47,64-111 env CLASHER_ROOT={target} PYTHONPATH={target}/src:{target}/engine-rs /mpac/sdicks02/repos/clasher/.venv/bin/python -B {target}/reports/explore/search-ab/home_worker.py --offset {task["offset"]} --workers 80 --max-seconds 540'
  if host=='127x04':
   workers=40
   cmd=f'bash /mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/fleet/fleet_run.sh {label} taskset -c 0-39 env CLASHER_ROOT={target} PYTHONPATH={target}/src:{target}/engine-rs {target}/.venv/bin/python -B {target}/reports/explore/search-ab/home_worker.py --offset {task["offset"]} --workers 40 --max-seconds 840 --gpu-guard --process-cap 90'
  if host=='127x08':
   workers=16
   cmd=f'bash /mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/fleet/fleet_run.sh {label} nice -n 9 taskset -c 64-79 env CLASHER_ROOT={target} PYTHONPATH={target}/src:{target}/engine-rs /mpac/sdicks02/repos/clasher/.venv/bin/python -B {target}/reports/explore/search-ab/home_worker.py --offset {task["offset"]} --workers 16 --max-seconds 840 --gpu-guard --process-cap 90'
  if task.get('case_file'):cmd+=' --case-file '+shlex.quote(target+'/reports/explore/search-ab/shards/'+name+'/schedule.json')+' --case-costs '+shlex.quote(target+'/reports/explore/search-ab/shards/'+name+'/case-costs.json')
  cmd+=' --out '+shlex.quote(target+'/reports/explore/search-ab/shards/'+name)
  cmd+=' --pairs '+str(task['pairs'])+' --throughput-log '+shlex.quote(job['log_path'])+' --throughput-field '+shlex.quote(job['field'])+' --baseline-rate '+str(job['baseline'])+' --gpu-pid '+str(job['pid'])+' --no-full-decision-latency'
  if '--gpu-guard' not in cmd:cmd+=' --gpu-guard'
  cmd=cmd.replace(' taskset -c',' chrt --idle 0 taskset -c')
  launch=run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,cmd]);record=dict(host=host,label=label,admitted=launch.returncode==0,response=launch.stdout,error=launch.stderr);records.append(record)
  print(json.dumps(record),flush=True)
  if launch.returncode:
   refused=host not in ('127x04','127x08') and launch.returncode!=255
   if lane_failed(lane_failures,host,admission_refused=refused):disabled.append(host)
   queue.insert(0,task)
  else:
   active[host]={**task,'host':host,'label':label,'workers':workers}
   if host!='127x03':print(run(['ssh','-o','BatchMode=yes',host,'nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader']).stdout,flush=True)
  save()
 save()
 if queue and not active and all(h in disabled for h in hosts):break
 time.sleep(30)
save()
if queue or active:raise SystemExit('scheduler incomplete; inspect receipts')
print('all 16 reporting shards complete',flush=True)
