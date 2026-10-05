"""Supplement the registration audit with embedded NPZ metadata and report text."""
import datetime
import json
from pathlib import Path
import re
import subprocess
import numpy as np
from qualify import write

HERE=Path(__file__).resolve().parent
schedule=json.loads((HERE/'schedule.json').read_text())['pairs']
proposed={r['seed'] for r in schedule};files=[];errors=[];overlap=[];metadata_seeds=0
for path in sorted(Path('reports').rglob('*.npz')):
    try:
        with np.load(path,allow_pickle=False) as z:
            found=set()
            for key in z.files:
                found.update(int(s) for s in re.findall(r'seed[_-]?(\d+)',key,re.I))
                if not any(t in key.lower() for t in ('meta','config','seed','json')):continue
                a=z[key]
                if a.dtype.kind in ('U','S'):
                    for text in a.reshape(-1):
                        if isinstance(text,bytes):text=text.decode()
                        found.update(int(s) for s in re.findall(r'"[A-Za-z_]*seed"\s*:\s*(\d+)',str(text)))
                elif 'seed' in key.lower() and a.dtype.kind in ('i','u'):
                    found.update(map(int,a.reshape(-1)))
            metadata_seeds+=len(found)
            if found:files.append(dict(path=str(path),seeds=sorted(found)))
            overlap.extend(dict(path=str(path),seed=s) for s in found&proposed)
    except Exception as e:errors.append(dict(path=str(path),error=str(e)))
pattern=r'(?<!\d)(?:'+'|'.join(map(str,sorted(proposed)))+r')(?!\d)'
proc=subprocess.run(['rg','--pcre2','--hidden','--no-ignore','--no-heading','--with-filename','--only-matching',pattern,'reports',
    '-g','*.json','-g','*.jsonl','-g','*.log','-g','*.md','-g','*.txt','-g','*.toml','-g','*.yaml','-g','*.yml','-g','*.csv','-g','*.tsv','-g','*.py','-g','*.sh',
    '-g','!reports/strategy_council_20260928/engine-speed/stage5/**','-g','!reports/strategy_council_20260928/engine-speed/PREREG-C56.md'],capture_output=True,text=True)
assert proc.returncode in (0,1),proc.stderr
text_matches=proc.stdout.splitlines()
result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=not(overlap or errors or text_matches),metadata_seed_occurrences=metadata_seeds,files=files,errors=errors,overlap=overlap,text_matches=text_matches)
write(HERE/'seed-audit-binary.json',result);print('metadata seeds',metadata_seeds,'archives with seeds',len(files),'passed',result['passed']);assert result['passed']
