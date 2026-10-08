"""Post-analysis accounting only: identify mirrored logs without changing frozen analysis."""
from pathlib import Path
import hashlib,json,re,shlex,subprocess
HERE=Path(__file__).resolve().parent
source=HERE/'compute-audit-before-attribution.json'
assert not source.exists();source.write_bytes((HERE/'compute-audit.json').read_bytes())
d=json.loads(source.read_text());records=d['records'];evidence=HERE/'cpu-log-evidence';evidence.mkdir(exist_ok=True)
foreign=[]
for r in records:
 declared=re.search(r'127x\d+',r['label']).group()
 if declared==r['host']:continue
 owner=next(x for x in records if x['host']==declared and x['label']==r['label'])
 copies={}
 for host in (r['host'],declared):
  data=subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,'cat',f"/mpac/sdicks02/jobs/clasher/{r['label']}.log"],timeout=30)
  assert hashlib.sha256(data).hexdigest()==(r if host==r['host'] else owner)['log_sha256']
  p=evidence/host;p.mkdir(exist_ok=True);(p/f"{r['label']}.log").write_bytes(data);copies[host]=data
 assert copies[declared].startswith(copies[r['host']]),(r['host'],r['label'])
 reason='byte-identical copy' if copies[declared]==copies[r['host']] else 'exact prefix of completed owner-host log'
 foreign.append(dict(host=r['host'],label=r['label'],owner_host=declared,reason=reason,copy_sha256=r['log_sha256'],owner_sha256=owner['log_sha256'],previously_counted_cpu_seconds=r['cpu_seconds']))
 r['excluded_as_mirrored_log']=True;r['owner_host']=declared;r['reason']=reason;r['cpu_seconds']=None;r['timing_missing']=False
own=[r for r in records if not r.get('excluded_as_mirrored_log')]
assert all(r['cpu_seconds'] is not None for r in own)
d.update(total_metered_cpu_hours=sum(r['cpu_seconds'] for r in own)/3600,confirmation_supervisors_and_workers_cpu_hours=sum(r['cpu_seconds'] for r in own if 'confirm-node' in r['label'])/3600,preflight_and_operations_cpu_hours=sum(r['cpu_seconds'] for r in own if 'confirm-node' not in r['label'])/3600,missing_timing=[],total_is_lower_bound=False,mirrored_logs_excluded=foreign,accounting='Host-specific detached labels. Wrong-host log copies are excluded after byte-identity/prefix checks against the owning host. Original aggregate and log evidence are retained. GNU time includes reaped children; game CPU overlaps. Small copying/finalization and unidentified mirror-process CPU are unmetered.')
(HERE/'compute-audit.json').write_text(json.dumps(d,indent=2)+'\n')
print(json.dumps({k:d[k] for k in ('total_metered_cpu_hours','game_cpu_hours','confirmation_supervisors_and_workers_cpu_hours','preflight_and_operations_cpu_hours','mirrored_logs_excluded')}))
