"""Host-specific detached labels; no copied remote logs misattributed to hub."""
from pathlib import Path
import hashlib,json,re,socket,subprocess
HERE=Path(__file__).resolve().parent;JOBS=Path('/mpac/sdicks02/jobs/clasher')
assert socket.gethostname().split('.')[0]=='127x01'
records=[]
for host in ('127x01','127x04','127x08'):
 command="python3 -c "+__import__('shlex').quote("from pathlib import Path;import json; p=Path('/mpac/sdicks02/jobs/clasher');print(json.dumps({f.name:f.read_text() for f in p.glob('s5-*.log')}))")
 logs={f.name:f.read_text() for f in JOBS.glob('s5-*.log')} if host=='127x01' else json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,command],text=True,timeout=30))
 for name,text in sorted(logs.items()):
  if re.match(r's5-confirm-\d+-',name):continue # reaped child CPU included in supervisor GNU time
  values=re.findall(r'^\t(?:User time \(seconds\)|System time \(seconds\)):\s*([0-9.]+)',text,re.M)
  assert len(values) in (0,2),(host,name)
  records.append(dict(host=host,label=name[:-4],log_sha256=hashlib.sha256(text.encode()).hexdigest(),cpu_seconds=sum(map(float,values)) if values else None,timing_missing=not values))
result=json.loads((HERE/'result.json').read_text())
out=dict(total_metered_cpu_hours=sum(r['cpu_seconds'] or 0 for r in records)/3600,game_cpu_hours=result['game_cpu_hours'],confirmation_supervisors_and_workers_cpu_hours=sum(r['cpu_seconds'] or 0 for r in records if 'confirm-node' in r['label'])/3600,preflight_and_operations_cpu_hours=sum(r['cpu_seconds'] or 0 for r in records if 'confirm-node' not in r['label'])/3600,missing_timing=[r for r in records if r['timing_missing']],total_is_lower_bound=any(r['timing_missing'] for r in records),records=records,accounting='Top-level GNU time includes reaped children. Game CPU overlaps and must not be added. Failed commands included. Small copying/final summaries are unmetered.')
(HERE/'compute-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='records'}))
