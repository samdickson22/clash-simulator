"""Lightweight run receipt monitor; does not inspect outcomes or change workers."""
import json,time,datetime,sys,os
from pathlib import Path
if len(sys.argv)>1: time.sleep(min(55,float(sys.argv[1])))
p=Path(__file__).resolve().parent
rows=[json.loads(f.read_text()) for f in (p/'games').glob('*/*.json')]
errors=[f.name for f in (p/'logs').glob('eval-v4-*.log') if 'Traceback' in f.read_text()]
record=dict(revision=json.loads((p/'manifest.json').read_text()).get('revision'),utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),games=len(rows),
 errors=errors,wall_overruns=sum(r['wall_over_250ms'] for r in rows),cpu_overruns=sum(r['cpu_over_250ms'] for r in rows),
 rejected=sum(r['failed_actions'] for r in rows),max_wall=max([r['decision_wall_max'] for r in rows] or [0]),
 done_workers=len(list((p/'results').glob('worker-*-done.json'))))
with (p/'results/monitor.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
print(json.dumps(record))
