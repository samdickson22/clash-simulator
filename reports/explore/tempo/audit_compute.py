"""Completed-game lower-bound compute and own-job scheduling receipts."""
import json
from collections import defaultdict
from pathlib import Path
root=Path(__file__).resolve().parent;hosts=defaultdict(lambda:dict(games=0,worker_cpu_seconds=0.,sim_wall_seconds=0.,declared_worker_wall_seconds=0.,attempt_wall_seconds=0.,attempts=0,guard_samples=0,measured_guard_samples=0,paused_samples=0,rate_ratios=[]))
origins={};seen=set();scheduler={}
for phase in ('combination','reporting'):
 f=root/f'receipts/{phase}-scheduler.json'
 if f.exists():scheduler[phase]=json.loads(f.read_text())
intervals=[]
for phase,s in scheduler.items():
 exits={r['label']:r['utc'] for r in s['records'] if r.get('event')=='exit'}
 for rec in s['records']:
  if rec.get('event')=='launch' and rec.get('status')==0:
   name=rec['label'].split('-')[2];intervals.append((phase,name,rec['host'],rec['utc'],exits.get(rec['label'],float('inf'))))
for base,host in [(root/'tuning','127x03'),(root/'smoke','127x04'),(root/'early-reporting','127x04')]+[(root/'early-leases'/h,h) for h in ('127x09','127x13','127x14','127x15','127x16')]:
 for f in (base/'games').glob('*.json'):
  r=json.loads(f.read_text());key=(r['metadata']['seed'],r['cohort']);origins[key]=host
correction_path=root/'receipts/hw-correction.json'
correction=json.loads(correction_path.read_text()) if correction_path.exists() else None
if correction:
 for item in correction['superseded_games']:origins[(item['seed'],'HW')]=correction['rerun_host']
for phase,s in scheduler.items():
 for task in s['completed']:
  for f in (root/phase/task['name']/'games').glob('*.json'):
   r=json.loads(f.read_text());key=(r['metadata']['seed'],r['cohort']);
   if key not in origins:
    matches=[h for p,n,h,b,e in intervals if p==phase and n==task['name'] and b<=f.stat().st_mtime<=e]
    assert len(matches)==1,(str(f),f.stat().st_mtime,matches)
    origins[key]=matches[0]
for f in root.glob('**/games/*.json'):
 if '/runtime/' in str(f):continue
 r=json.loads(f.read_text());key=(r['metadata']['seed'],r['cohort'])
 if key in seen:continue
 seen.add(key);host=origins.get(key,'unknown');row=hosts[host];row['games']+=1;row['worker_cpu_seconds']+=r['cpu_seconds'];row['sim_wall_seconds']+=r['wall_seconds']
guard_seen=set()
for f in root.glob('**/gpu-guard.jsonl'):
 receipt=f.parent/'receipt.json';runtime=f.parent/'worker-runtime.json'
 host=json.loads(receipt.read_text())['host'] if receipt.exists() else f.parent.name if f.parent.name.startswith('127x') else 'unknown';row=hosts[host]
 for line in f.read_text().splitlines():
  try:s=json.loads(line)
  except ValueError:continue
  key=(s['utc'],s.get('event'),s.get('throughput'))
  if key in guard_seen:continue
  guard_seen.add(key)
  actual_host=host
  for phase,name,attempt_host,begin,end in intervals:
   if f.parent.name==name and f.parent.parent.name==phase and begin<=s['utc']<=end:actual_host=attempt_host;break
  row=hosts[actual_host]
  row['guard_samples']+=1;row['paused_samples']+=s.get('paused',False)
  if s.get('throughput') is not None and s.get('baseline'):
   row['measured_guard_samples']+=1;row['rate_ratios'].append(s['throughput']/s['baseline'])
for f in (root/'receipts/attempts').glob('127x*/**/worker-runtime.json'):
 host=f.relative_to(root/'receipts/attempts').parts[0];runtime=json.loads(f.read_text());row=hosts[host];row['declared_worker_wall_seconds']+=runtime['workers']*runtime['wall_seconds'];row['attempt_wall_seconds']+=runtime['wall_seconds'];row['attempts']+=1
for host,row in hosts.items():
 row['completed_cpu_over_declared_worker_wall_lower_bound']=(row['worker_cpu_seconds']/row['declared_worker_wall_seconds'] if row['declared_worker_wall_seconds'] else None)
 ratios=row.pop('rate_ratios');ratios.sort();row['own_gpu_rate_ratio_min_median']=([ratios[0],ratios[len(ratios)//2]] if ratios else None)
records=[rec for s in scheduler.values() for rec in s['records']];refusals=[rec for rec in records if rec['event']=='launch' and rec['status']]
result=dict(completed_unique_games=len(seen),completed_worker_cpu_seconds=sum(r['worker_cpu_seconds'] for r in hosts.values()),per_host=dict(hosts),admission_refusals=refusals,worker_caps={'127x04':40,'127x03':96,'127x09':20,'127x13':20,'127x14':20,'127x15':20,'127x16':40},limit_note='worker caps exclude declared supervisor overhead; wrapper r3 enforces combined admission',cpu_accounting='completed unique games only; excludes initialization, reducers, monitors and unfinished attempts; lower bound',guard='own interval throughput below95% only; GPU utilization never a pause trigger',no_disallowed_hosts=True,game_origin_accounting='early receipts, then preserved per-game file mtime matched to exactly one scheduler attempt interval; corrected HW explicitly09',guard_accounting='deduplicated UTC samples; resumed shard histories attributed by recorded attempt host/time',utilization_note='completed unique game CPU / declared workers times attempt wall, including startup/guard pauses; a lower bound, not measured hardware occupancy',known_unfinished_cpu_seconds=sum(json.loads(f.read_text()).get('stopped_sim_cpu_seconds',0) for f in (root/'receipts').rglob('baseline-recalibration-*.json')))
if correction:
 result['superseded_definition_games']=len(correction['superseded_games'])
 result['superseded_definition_cpu_seconds']=sum(x['cpu_seconds'] for x in correction['superseded_games'])
 result['physical_completed_game_instances']=result['completed_unique_games']+result['superseded_definition_games']
 result['physical_completed_cpu_seconds_lower_bound']=result['completed_worker_cpu_seconds']+result['superseded_definition_cpu_seconds']
 result['correction_receipt']='receipts/hw-correction.json; invalid HW instances retained outside the analysis games tree'
(root/'compute-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('admission_refusals','per_host')}))
