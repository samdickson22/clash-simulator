"""Successful new-game throughput, excluding reused rows by atomic-write mtime."""
import datetime,json,shlex,subprocess,time
from pathlib import Path
root=Path(__file__).resolve().parent;s=json.loads((root/'receipts/lease-scheduler.json').read_text());results=[]
for host,t in s['active'].items():
 if host not in ('127x09','127x14'):continue
 label=t['label'];name=t['name'];remote='/mpac/sdicks02/repos/clasher-lease'
 code=f'''import datetime,json,time;from pathlib import Path
s=json.loads(Path({remote+'/jobs/'+label+'.state.json'!r}).read_text());start=datetime.datetime.fromisoformat(s['started_utc']).timestamp();files=list(Path({remote+'/search-ab-runtime/reports/explore/search-ab/shards/'+name+'/games'!r}).glob('*.json'));fresh=sum(p.stat().st_mtime>=start for p in files);print(json.dumps(dict(start=start,now=time.time(),completed=len(files),fresh=fresh,command=s['command'],declared_processes=s['declared_processes'],pss_bytes=s['pss_bytes'])))'''
 r=subprocess.run(['ssh','-o','BatchMode=yes',host,'python3 -c '+shlex.quote(code)],text=True,capture_output=True,timeout=20)
 if r.returncode:results.append(dict(host=host,error=r.stderr));continue
 d=json.loads(r.stdout);elapsed=d['now']-d['start'];workers=t['workers'];results.append(dict(host=host,label=label,workers=workers,elapsed_seconds=elapsed,new_games=d['fresh'],reused_games=d['completed']-d['fresh'],fresh_games_per_second=d['fresh']/elapsed,normalized_96_worker_rate=96/workers*d['fresh']/elapsed,command=d['command'],declared_processes=d['declared_processes'],pss_bytes=d['pss_bytes']))
out=dict(measured_utc=time.time(),method='successful atomic JSON writes newer than current launcher UTC; rsync -a preserves reused mtimes',runs=results);(root/'receipts/throughput-after-affinity.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
