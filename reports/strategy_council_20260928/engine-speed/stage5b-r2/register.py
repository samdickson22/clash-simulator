"""Audit all report seed provenance, then freeze 192 paired human matchups."""
import datetime
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import numpy as np
from decks import catalogs, family, ROLES, INDEX, CATALOG
from qualify import write

HERE = Path(__file__).resolve().parent
BASE = 4023180111
worlds = [BASE+1009*i for i in range(192)]
proposed = {s+offset for s in worlds for offset in (0,100000,100001,100002)}
assert len(proposed) == 768
used=set(); fields=0; overlap=[]; errors=[]
proc=subprocess.Popen(['rg','--hidden','--no-ignore','--no-heading','--with-filename','--only-matching',r'"[A-Za-z_]*seed"\s*:\s*[0-9]+','reports','-g','*.json','-g','*.jsonl','-g','!**/stage5b-r2/**'],stdout=subprocess.PIPE,text=True)
for line in proc.stdout:
    m=re.search(r':\s*(\d+)\s*$',line)
    if m:
        seed=int(m[1]);fields+=1;used.add(seed)
        if seed in proposed:overlap.append(line.strip())
assert proc.wait() in (0,1)
archives=0;metadata_seeds=0
for path in sorted(Path('reports').rglob('*.npz')):
    try:
        with np.load(path,allow_pickle=False) as z:
            archives+=1;found=set()
            for key in z.files:
                found.update(int(s) for s in re.findall(r'seed[_-]?(\d+)',key,re.I))
                if not any(t in key.lower() for t in ('meta','config','seed','json')):continue
                a=z[key]
                if a.dtype.kind in ('U','S'):
                    for text in a.reshape(-1):
                        if isinstance(text,bytes):text=text.decode()
                        found.update(int(s) for s in re.findall(r'"[A-Za-z_]*seed"\s*:\s*(\d+)',str(text)))
                elif 'seed' in key.lower() and a.dtype.kind in ('i','u'):found.update(map(int,a.reshape(-1)))
            used.update(found);metadata_seeds+=len(found)
            overlap.extend(f'{path}: {s}' for s in found & proposed)
    except Exception as e:errors.append([str(path),str(e)])
pattern=r'(?<!\d)(?:'+'|'.join(map(str,sorted(proposed)))+r')(?!\d)'
proc=subprocess.run(['rg','--pcre2','--hidden','--no-ignore','--no-heading','--with-filename','--only-matching',pattern,'reports','-g','*.json','-g','*.jsonl','-g','*.log','-g','*.md','-g','*.txt','-g','*.toml','-g','*.yaml','-g','*.csv','-g','*.tsv','-g','*.py','-g','*.sh','-g','!**/stage5b-r2/**'],capture_output=True,text=True)
assert proc.returncode in (0,1),proc.stderr
overlap += proc.stdout.splitlines()
audit=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),seed_fields=fields,unique_seeds=len(used),npz_archives=archives,metadata_seeds=metadata_seeds,overlap=overlap,errors=errors,passed=not(overlap or errors),proposed=sorted(proposed))
write(HERE/'seed-audit.json',audit);assert audit['passed'],(overlap,errors)
cats=catalogs();held={}
for role in ('eval','eval_ood'):
    for d in cats[role]['decks']:held[tuple(d['cards'])]=held.get(tuple(d['cards']),0)+d['frequency']
supported={tuple(sorted(d['cards'])) for d in cats['train']['decks']}
held=[dict(cards=list(d),frequency=n) for d,n in held.items() if tuple(sorted(d)) in supported]
rng=random.Random(4023100001)
def choose(rows):return rng.choices(rows,weights=[r['frequency'] for r in rows],k=1)[0]
schedule=[];families=['Hog 2.6','Hog EQ/Firecracker/MM','Royal Hogs/Furnace','X-Bow','bait','Goblinstein','AQ']
for mode,counts in [('head-to-head',[19,19,18,18,18,18,18]),('scripts',[10,9,9,9,9,9,9])]:
    for f,count in zip(families,counts):
        pool=[d for d in held if family(d['cards'])==f];assert pool
        for _ in range(count):
            i=len(schedule);own=list(choose(pool)['cards']);other=list(choose(cats['train']['decks'])['cards'])
            rng.shuffle(own);rng.shuffle(other)
            schedule.append(dict(pair=i,mode=mode,seed=worlds[i],family=f,style=('balanced','pressure','defense')[i%3],planning_deck=own,opponent_deck=other))
assert len(schedule)==192
path=HERE/'schedule.json';assert not path.exists()
write(path,dict(utc=audit['utc'],pairs=schedule,sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROLES,INDEX,CATALOG,HERE.parent/'PREREG-C56-deadline-r2.md')},seed_audit_sha256=hashlib.sha256((HERE/'seed-audit.json').read_bytes()).hexdigest()))
print('registered',len(schedule),'pairs; seed fields',fields,'archives',archives,flush=True)
