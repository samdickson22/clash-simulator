"""First ten-minute game throughput and scheduler/guard accounting."""
import argparse,json,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--start-utc',type=float,required=True);a=p.parse_args()
rows=[]
for f in a.root.glob('**/games/*.json'):
 r=json.loads(f.read_text());rows.append((f.stat().st_mtime,r['cpu_seconds'],r['wall_seconds']))
now=time.time();elapsed=now-a.start_utc;early=[r for r in rows if r[0]<=a.start_utc+600]
guard=[]
for f in a.root.glob('**/gpu-guard.jsonl'):
 for line in f.read_text().splitlines():
  try:guard.append(json.loads(line))
  except ValueError:pass
rates=[v['throughput']/v['baseline'] for v in guard if v.get('throughput') is not None and v.get('baseline')]
result=dict(elapsed_seconds=elapsed,completed_games=len(rows),games_per_second=len(rows)/elapsed,first10_minutes_games=len(early),first10_minutes_games_per_second=len(early)/min(elapsed,600),completed_worker_cpu_seconds=sum(r[1] for r in rows),guard_samples=len(guard),measured_guard_samples=len(rates),pause_samples=sum(r['paused'] for r in guard),rate_ratio_min=min(rates) if rates else None)
a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
