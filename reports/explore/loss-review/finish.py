"""Bounded completion on the allowed home CPU host; never starts duplicate sims."""
import subprocess,time
from pathlib import Path
root=Path('/mpac/sdicks02/repos/clasher');base=root/'reports/explore/loss-review'
for attempt in range(120):
    p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','127x01',
        'cat /mpac/sdicks02/jobs/clasher/loss-review-sim-production-v1.exit'],capture_output=True,text=True)
    if p.returncode==0:
        if p.stdout.strip()!='0':raise RuntimeError('simulation failed: '+p.stdout)
        break
    time.sleep(10)
else:raise RuntimeError('simulation wait exceeded 20 minutes')
subprocess.run(['rsync','-rc','127x01:'+str(base/'sim-production-v1'),str(base)+'/'],check=True)
python=str(root/'.venv/bin/python')
subprocess.run([python,'-m','clasher.analysis.loss_review.reduce_traces','--source',str(base/'sim-production-v1'),
    '--out',str(base/'sim-reduced-v1/games'),'--workers','64'],check=True)
subprocess.run([python,'-m','clasher.analysis.loss_review.summarize','--inputs',str(base/'human-train-v3/games.jsonl'),
    str(base/'human-dev-v3/games.jsonl'),str(base/'sim-reduced-v1/games'),
    '--out',str(base/'results.json'),'--workers','64','--bootstrap','1000'],check=True)
