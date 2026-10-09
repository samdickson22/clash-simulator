"""Read-only compact progress; no game outcomes while runs are incomplete."""
import json
from pathlib import Path
import time

job=Path('/mpac/sdicks02/jobs/clasher/e1-20261009-r1')
result={'time':time.time()}
for phase in ('smoke','main','reserve'):
    root=job/phase
    if not root.exists():continue
    files=list((root/'games').glob('*.json'))
    row={'completed':len(files)}
    for name in ('receipt.json','supervisor-exit.json','pids.json'):
        f=root/name
        if f.exists(): row[name[:-5]]=json.loads(f.read_text())
    if 'pids' in row:
        row['supervisor_present']=Path('/proc/'+str(row['pids']['supervisor'])).exists()
        row['manager_present']=Path('/proc/'+str(row['pids']['child_pgid'])).exists()
    result[phase]=row
p=job/'progress.json'
if p.exists():result['progress']=json.loads(p.read_text())
print(json.dumps(result))
