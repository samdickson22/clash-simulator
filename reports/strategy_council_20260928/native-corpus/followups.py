import json,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
for _ in range(120):
 p=HERE/'benchmark.jsonl'
 if p.exists() and len(p.read_text().splitlines())==16:break
 time.sleep(5)
else:raise RuntimeError('benchmark did not complete within bounded wait')
for script in ['infer_order.py','diagnostics.py','public_benchmark.py']:
 with (HERE/(script+'.log')).open('w') as log:
  r=subprocess.run([str(HERE.parents[2]/'.venv/bin/python'),str(HERE/script)],stdout=log,stderr=subprocess.STDOUT)
 with (HERE/'PROGRESS.md').open('a') as log:log.write(f'\nFollowup {script} exited {r.returncode} at {time.strftime("%Y-%m-%d %H:%M:%S")}.\n')
 if r.returncode:raise RuntimeError(f'{script} failed')
(HERE/'followups-complete.json').write_text(json.dumps({'complete':True,'time':time.time()})+'\n')
