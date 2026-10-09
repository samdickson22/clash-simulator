"""Short-shard fleet scheduler; v2 lease admission, no duplicate active cases."""
import argparse,datetime,json,os,shlex,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['reporting','combination'],default='reporting');p.add_argument('--selection',type=Path,required=True);p.add_argument('--resume-state',action='store_true');p.add_argument('--resume-hosts',nargs='*',default=[]);a=p.parse_args()
root=Path(__file__).resolve().parents[3];report=root/'reports/explore/tempo';state_path=report/'receipts'/f'{a.phase}-scheduler.json'
early_leases=json.loads((report/'receipts/early-leases-launch.json').read_text()) if (report/'receipts/early-leases-launch.json').exists() else []
early_by_host={r['host']:r['label'] for r in early_leases if r.get('status')==0}
selection=json.loads(a.selection.read_text());arms=['0','E','H12','H16','W','BEST'] if a.phase=='reporting' else ['0','EH','EW','HW','EHW']
if a.phase=='reporting':arms[-1]=selection.get('combination_arm','EHW')
pairs=1000 if a.phase=='reporting' else 150;seed_offset=70010 if a.phase=='reporting' else 85000
hosts=['127x04','127x03','127x09','127x13','127x14','127x15','127x16'];caps=dict(zip(hosts,[40,96,20,20,20,20,28]))
remote={h:'/mpac/sdicks02/repos/clasher' if h=='127x04' else '/mpac/sdicks02/repos/clasher-tempo-runtime' if h=='127x03' else '/mpac/sdicks02/repos/clasher-lease/tempo-runtime' for h in hosts}
grain=50 if a.phase=='reporting' else 25
if a.phase=='reporting' and not state_path.exists():
 # Consolidate completed early games into reporting's larger short shards.
 folder=report/'reporting'
 for prior in sorted(folder.glob('p*')):
  offset=int(prior.name[1:]);target=folder/f'p{offset//grain*grain:04d}'
  if target==prior:continue
  (target/'games').mkdir(parents=True,exist_ok=True)
  for game in (prior/'games').glob('*.json'):
   dest=target/'games'/game.name
   if dest.exists():raise ValueError('duplicate early game')
   game.replace(dest)
  (prior/'games').rmdir();prior.rmdir()
queue=[dict(name=f'p{i:04d}',offset=i,pairs=min(grain,pairs-i)) for i in range(0,pairs,grain)];active={};completed=[];records=[];failures={};attempts={};disabled=[];start=time.time()
if state_path.exists():
 if not a.resume_state:raise SystemExit('Existing scheduler state; do not duplicate active work')
 prior=json.loads(state_path.read_text());assert prior['arms']==arms and prior['selection']==selection
 queue=prior['queue'];active=prior['active'];completed=prior['completed'];records=prior['records'];disabled=prior['disabled'];start=prior['started_utc']
 for rec in records:
  if rec.get('event')=='launch':
   name=rec['label'].split('-')[2];attempt=int(rec['label'].rsplit('-r',1)[1]);attempts[name]=max(attempts.get(name,0),attempt)
def run(host,args,timeout=60):
 args=['nice','-n','10','chrt','--idle','0',*args]
 command=args if host=='127x04' else ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,shlex.join(args)]
 return subprocess.run(['nice','-n','10','chrt','--idle','0',*command],text=True,capture_output=True,timeout=timeout)
def save():
 value=dict(phase=a.phase,arms=arms,pairs=pairs,seed_offset=seed_offset,selection=selection,started_utc=start,active=active,queue=queue,completed=completed,records=records,disabled=disabled)
 tmp=state_path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(state_path)
def guard_args(host):
 if host=='127x03':return []
 path=report/'receipts/perception-rate.baseline.json' if host=='127x04' else Path(remote[host])/'reports/explore/tempo/receipts/perception-rate.baseline.json'
 if host=='127x16':
  cfg=run(host,['cat','/mpac/sdicks02/repos/clasher-lease/delay-fixes-runtime/reports/explore/delay-fixes/guard-config.json'])
  if cfg.returncode==0:
   jobs=json.loads(cfg.stdout)['jobs']
   if jobs:
    job=jobs[0];return ['--gpu-guard','--throughput-log',job['log_path'],'--throughput-field',job['field'],'--baseline-rate',str(job['baseline']),'--gpu-pid',str(job['pid'])]
 cfg=run(host,['cat',str(path)])
 if cfg.returncode:return None
 job=json.loads(cfg.stdout)
 if job['baseline']<=0:return None
 return ['--gpu-guard','--throughput-log',job['log_path'],'--throughput-field',job['field'],'--baseline-rate',str(job['baseline'])]
def launch(host,task):
 if host not in ('127x03','127x04') and datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime(2026,10,9,4,15,tzinfo=datetime.timezone.utc):return False,'lease admission window closed'
 target=remote[host];workers=caps[host];label=f'tempo-{a.phase}-{task["name"]}-{host}-r{attempts.get(task["name"],0)+1}';attempts[task['name']]=attempts.get(task['name'],0)+1
 guards=guard_args(host)
 if guards is None:return False,'missing measured throughput baseline'
 command=['nice','-n','10','chrt','--idle','0','taskset','-c','0-47,64-111' if host in ('127x03','127x04') else f'64-{63+workers}','env',f'CLASHER_ROOT={target}',f'PYTHONPATH={target}/src:{target}/engine-rs','RAYON_NUM_THREADS=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1',('/mpac/sdicks02/repos/clasher-lease/repo/.venv/bin/python' if host not in ('127x03','127x04') else '/mpac/sdicks02/repos/clasher/.venv/bin/python'),'-B',target+'/reports/explore/tempo/worker_runtime.py','--offset',str(task['offset']),'--pairs',str(task['pairs']),'--seed-offset',str(seed_offset),'--workers',str(workers),'--arms',*arms,'--elixir-weight',str(selection['elixir_weight']),'--wait-prior',str(selection['wait_prior']),'--combo-horizon',str(selection['combo_horizon']),'--out',target+f'/reports/explore/tempo/{a.phase}/{task["name"]}','--max-seconds','840','--case-costs',target+'/reports/explore/tempo/case-costs.json',*guards]
 if host in ('127x03','127x04'):
  if host=='127x03' and run(host,['test','!','-e','/mpac/sdicks02/jobs/clasher/GATES-03-RESERVED']).returncode:return False,'03 reserved'
  command=['bash','/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/fleet/fleet_run.sh',label,*command]
 else:
  # Count the wrapper, runtime supervisor, simulator parent and worker pool.
  command=['bash','/mpac/sdicks02/repos/clasher-lease/run_v2.sh','--max-processes',str(workers+4),'--expected-pss-gb',str(round(workers*.7+2,1)),label,'--',*command]
 result=run(host,command,90);records.append(dict(event='launch',utc=time.time(),host=host,label=label,command=command,status=result.returncode,stdout=result.stdout,stderr=result.stderr))
 if result.returncode:return False,'admission refusal' if host not in ('127x03','127x04') and result.returncode!=255 else 'launch failure'
 active[host]=dict(task,label=label,workers=workers,host=host,started=time.time());return True,'admitted'
for host in a.resume_hosts:
 if host not in ('127x09','127x13','127x14','127x15'):raise ValueError('controlled capture refresh only')
 proof=run(host,['cat',remote[host]+'/reports/explore/tempo/receipts/baseline-idle-refresh.json'])
 proof.check_returncode();control=json.loads(proof.stdout)
 if control['seconds']<170 or time.time()-control['utc']>600:raise ValueError('fresh unloaded control required')
 if host in disabled:disabled.remove(host)
 records.append(dict(event='controlled unloaded rate refresh; lane reopened',host=host,utc=time.time(),new_baseline=control['new_baseline'],control_seconds=control['seconds']))
save()
while queue or active:
 if time.time()-start>9000:
  records.append(dict(event="bounded controller time reached",utc=time.time()));break
 now=datetime.datetime.now(datetime.timezone.utc);leases_open=now<datetime.datetime(2026,10,9,4,15,tzinfo=datetime.timezone.utc)
 for host in hosts:
  if host in active:
   task=active[host];label=task['label'];jobfile='/mpac/sdicks02/jobs/clasher/'+label+'.exit' if host in ('127x03','127x04') else '/mpac/sdicks02/repos/clasher-lease/jobs/'+label+'.exit.json'
   status=run(host,['cat',jobfile])
   if status.returncode:
    if host not in ('127x03','127x04') and time.time()-task['started']>300 and not task.get('drain_requested'):
     target=remote[host]+f'/reports/explore/tempo/{a.phase}/{task["name"]}'
     sample=run(host,['tail','-1',target+'/gpu-guard.jsonl'])
     if sample.returncode==0:
      guard=json.loads(sample.stdout)
      if guard.get('paused') and time.time()-guard['utc']<10:
       drain=run(host,['/usr/bin/python3',remote[host]+'/reports/explore/tempo/drain_shard.py','--label',label,'--out',target])
       records.append(dict(event='stalled GPU-paused shard drain',utc=time.time(),host=host,label=label,status=drain.returncode,stdout=drain.stdout,stderr=drain.stderr))
       if drain.returncode==0:task['drain_requested']=True;save()
    continue
   target=remote[host]+f'/reports/explore/tempo/{a.phase}/{task["name"]}'
   dest=report/a.phase/task['name'];dest.mkdir(parents=True,exist_ok=True)
   if host!='127x04':
    fetch=subprocess.run(['nice','-n','10','chrt','--idle','0','rsync','--rsync-path=nice -n 10 chrt --idle 0 rsync','-ac',f'{host}:{target}/',str(dest)+'/'],text=True,capture_output=True,timeout=120)
    if fetch.returncode:records.append(dict(event='fetch failed',host=host,error=fetch.stderr));continue
   receipt=dest/'receipt.json';done=receipt.exists() and json.loads(receipt.read_text()).get('games')==task['pairs']*len(arms)
   records.append(dict(event='exit',utc=time.time(),host=host,label=label,exit=status.stdout,complete=done))
   if done:completed.append(task);failures[host]=0
   else:
    queue.insert(0,{k:task[k] for k in ('name','offset','pairs')});failures[host]=failures.get(host,0)+1
    if failures[host]>=3 or task.get('drain_requested'):disabled.append(host)
   del active[host];save()
  if host in disabled or not queue or host not in ('127x03','127x04') and not leases_open:continue
  if host=='127x04':
   parity_pid=run(host,['test','-e','/mpac/sdicks02/jobs/clasher/tempo-parity-v1.pid'])
   if parity_pid.returncode==0 and run(host,['test','-e','/mpac/sdicks02/jobs/clasher/tempo-parity-v1.exit']).returncode:continue
  if host in early_by_host:
   early_exit=run(host,['test','-e','/mpac/sdicks02/repos/clasher-lease/jobs/'+early_by_host[host]+'.exit.json'])
   if early_exit.returncode:continue
   del early_by_host[host]
  task=queue[0]
  # Previously partially completed shards are copied before resuming elsewhere.
  dest=report/a.phase/task['name']
  if dest.exists() and host!='127x04':
   run(host,['mkdir','-p',remote[host]+f'/reports/explore/tempo/{a.phase}/{task["name"]}']).check_returncode()
   subprocess.run(['nice','-n','10','chrt','--idle','0','rsync','--rsync-path=nice -n 10 chrt --idle 0 rsync','-ac',str(dest)+'/',f'{host}:{remote[host]}/reports/explore/tempo/{a.phase}/{task["name"]}/'],check=True,timeout=120)
  ok,reason=launch(host,task)
  if ok:queue.pop(0)
  else:
   records.append(dict(event=reason,host=host,utc=time.time()))
   if reason=='admission refusal':disabled.append(host)
   elif reason=='launch failure':
    failures[host]=failures.get(host,0)+1
    if failures[host]>=3:disabled.append(host)
  save()
 if not active and all(h in disabled for h in ('127x03','127x04')) and not leases_open:break
 time.sleep(20)
save();print(json.dumps(dict(completed=len(completed),queued=len(queue))),flush=True)
