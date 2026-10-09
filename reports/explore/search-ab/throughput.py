"""Read only this experiment's active shard outputs and v2 state receipts."""
import json,subprocess,time
from pathlib import Path
root=Path(__file__).resolve().parent;s=json.loads((root/'receipts/lease-scheduler.json').read_text());result=[]
for host,t in s['active'].items():
 label=t['label'];name=t['name'];remote='/mpac/sdicks02/repos/clasher-lease'
 code='import json,time;from pathlib import Path;s=json.loads(Path("'+remote+'/jobs/'+label+'.state.json").read_text());n=len(list(Path("'+remote+'/search-ab-runtime/reports/explore/search-ab/shards/'+name+'/games").glob("*.json")));print(json.dumps(dict(state=s,completed_games=n,now=time.time())))'
 r=subprocess.run(['ssh','-o','BatchMode=yes',host,'/usr/bin/python3 -c '+__import__('shlex').quote(code)],text=True,capture_output=True,timeout=20)
 if r.returncode:result.append(dict(host=host,error=r.stderr));continue
 d=json.loads(r.stdout);state=d['state'];start=__import__('datetime').datetime.fromisoformat(state['started_utc']).timestamp();elapsed=d['now']-start;fresh=d['completed_games']-t['retained_home_games']
 result.append(dict(host=host,label=label,workers=36,declared_processes=state['declared_processes'],declared_pss_bytes=state['declared_pss_bytes'],completed_games=d['completed_games'],retained_games=t['retained_home_games'],elapsed_seconds=elapsed,fresh_games_per_second=fresh/elapsed,normalized_96_worker_rate=96/36*fresh/elapsed,state_keys=list(state),state=state))
out=root/'receipts/throughput.json';out.write_text(json.dumps(dict(measured_utc=time.time(),active_runs=result),indent=2)+'\n');print(json.dumps([{k:v for k,v in r.items() if k not in ('state','state_keys')} for r in result]))
