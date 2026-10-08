"""Non-overlapping top-level detached-command CPU totals."""
from pathlib import Path
import hashlib,json,re,socket,subprocess
HERE=Path(__file__).resolve().parent;JOBS='/mpac/sdicks02/jobs/clasher'
assert socket.gethostname().split('.')[0]=='127x01'
labels={h:['s4-snapshot-r1'] for h in ('127x01','127x04','127x08')}
labels['127x01']+=['s4-seed-audit-r1','s4-register-r1','s4-start-r1','s4-collect-r1']
labels['127x04']+=['s4-seed-audit-r1','s4-tests-r1','s4-recovery-tests-r1','s4-recovery-tests-r2','s4-exact-1-r1']+[f's4-preflight-{i}-r1' for i in (0,2,4,6)]
labels['127x08']+=['s4-tracker-tests-r1','s4-exact-0-r1','s4-exact-2-r1']+[f's4-preflight-{i}-r1' for i in (1,3,5,7)]
for h in ('127x04','127x08'):labels[h]+=['s4-dev-generate-r1','s4-dev-replay-v1',f's4-confirm-node-{h}-r1']
extra=HERE/'extra-metered-labels.json'
if extra.exists():
 for h,ls in json.loads(extra.read_text()).items():labels[h]+=ls
records=[];seen_logs={}
for host,ls in labels.items():
 for label in ls:
  if host=='127x01':text=(Path(JOBS)/f'{label}.log').read_text()
  else:text=subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,'cat',f'{JOBS}/{label}.log'],text=True,timeout=30)
  values=re.findall(r'^\t(?:User time \(seconds\)|System time \(seconds\)):\s*([0-9.]+)',text,re.M);assert len(values) in (0,2),(host,label,values)
  digest=hashlib.sha256(text.encode()).hexdigest();reason=None
  for line in text.splitlines():
   if line.startswith('{'):
    try:
     declared=json.loads(line).get('host')
     if isinstance(declared,str) and declared.startswith('127x') and declared!=host:reason=f'log declares {declared}, not {host}'
    except json.JSONDecodeError:pass
  if digest in seen_logs:reason=f'identical log bytes already attributed to {seen_logs[digest]}'
  else:seen_logs[digest]=host+'/'+label
  records.append(dict(host=host,label=label,log_sha256=digest,cpu_seconds=sum(map(float,values)) if values and reason is None else None,timing_missing=not values or reason is not None,reason=reason))
result=json.loads((HERE/'result.json').read_text())
out=dict(total_metered_cpu_hours=sum(r['cpu_seconds'] or 0 for r in records)/3600,game_cpu_hours=result['game_cpu_hours'],confirmation_supervisors_and_workers_cpu_hours=sum(r['cpu_seconds'] or 0 for r in records if 'confirm-node' in r['label'])/3600,dev_and_preflight_cpu_hours=sum(r['cpu_seconds'] or 0 for r in records if 'confirm-node' not in r['label'] and 'collect' not in r['label'])/3600,missing_timing=[r for r in records if r['timing_missing']],total_is_lower_bound=any(r['timing_missing'] for r in records),records=records,accounting='Top-level GNU time includes reaped children. Game CPU is a subset; do not add it to totals. Failed tests and interrupted development runs are included where GNU time survived. Missing timing is explicit; totals are lower bounds if any log lacks timing. Small SSH, copying and final summaries are unmetered.')
(HERE/'compute-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='records'}))
