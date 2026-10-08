"""Meter each top-level detached command once; child totals are overlapping."""
from pathlib import Path
import json,re,socket,subprocess
HERE=Path(__file__).resolve().parent;JOBS='/mpac/sdicks02/jobs/clasher'
assert socket.gethostname().split('.')[0]=='127x01'
labels={'127x01':['s3-seed-audit-01-v1','s3-collect-r1'],
 '127x04':['s3-seed-audit-04-v1','s3-inspect-v1','s3-tests-v1','s3-tests-v2','s3-tests-final','s3-equivalence-v1']+[f's3-replays-{i}-v1' for i in range(3)]+[f's3-pilot-{i}-final' for i in range(7)],'127x08':[]}
for host in ('127x04','127x08'):
 short=host[-2:]
 labels[host]+=[f's3-dev-generate-node{short}-v{i}' for i in (1,2)]+[f's3-dev-replay-node{short}-v{i}' for i in (1,2,3)]+[f's3-confirm-node-{host}-r1']
records=[]
for host,ls in labels.items():
 for label in ls:
  if host=='127x01':text=(Path(JOBS)/f'{label}.log').read_text()
  else:text=subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',host,'cat',f'{JOBS}/{label}.log'],text=True,timeout=30)
  values=re.findall(r'^\t(?:User time \(seconds\)|System time \(seconds\)):\s*([0-9.]+)',text,re.M)
  assert len(values)==2,(host,label,'missing/duplicate timing')
  records.append(dict(host=host,label=label,cpu_seconds=sum(map(float,values))))
result=json.loads((HERE/'result.json').read_text())
out=dict(total_metered_cpu_hours=sum(r['cpu_seconds'] for r in records)/3600,game_cpu_hours=result['game_cpu_hours'],
 confirmation_supervisors_and_workers_cpu_hours=sum(r['cpu_seconds'] for r in records if 'confirm-node' in r['label'])/3600,
 dev_and_preflight_cpu_hours=sum(r['cpu_seconds'] for r in records if 'confirm-node' not in r['label'] and 'collect' not in r['label'])/3600,
 records=records,accounting='Top-level /usr/bin/time totals include children. Game CPU is a subset, not additive. Small SSH/file-copy/hash/registration operations are unmetered.')
(HERE/'compute-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='records'}))
