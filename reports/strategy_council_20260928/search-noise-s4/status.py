"""One bounded outcome-blind status response per host."""
from pathlib import Path
import argparse,json,socket
HERE=Path(__file__).resolve().parent;JOBS=Path('/mpac/sdicks02/jobs/clasher')
ap=argparse.ArgumentParser();ap.add_argument('--attempt',default='r1');args=ap.parse_args()
host=socket.gethostname().split('.')[0];launch=HERE/f'launch-{host}-{args.attempt}.json'
out=dict(host=host,workers=[],supervisor=None,launch_exists=launch.exists())
label=f's4-confirm-node-{host}-{args.attempt}'
if (JOBS/f'{label}.exit').exists():
    out['supervisor']=dict(exit=(JOBS/f'{label}.exit').read_text().strip(),log=(JOBS/f'{label}.log').read_text())
if launch.exists():
    for worker in json.loads(launch.read_text())['workers']:
        i=worker['index'];p=JOBS/f'{worker["label"]}.exit'
        if p.exists():
            done=HERE/f'worker-{i}-done.json'
            out['workers'].append(dict(index=i,label=worker['label'],exit=p.read_text().strip(),done=json.loads(done.read_text()) if done.exists() else None,log=(JOBS/f'{worker["label"]}.log').read_text()))
print(json.dumps(out))
