"""Freeze the prospective schedule only after auditing historical game seeds."""
import datetime
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import numpy as np
from decks import catalogs,family,ROLES,INDEX,CATALOG
from qualify import write

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
FAMILIES=['Hog 2.6','Hog EQ/Firecracker/MM','Royal Hogs/Furnace','X-Bow','bait','Goblinstein','AQ']
BASE=3420718301
proposed={BASE+1009*i for i in range(128)}
# No ignore filters: archived/ignored reports remain part of the exclusion set.
proc=subprocess.Popen(['rg','--hidden','--no-ignore','--no-heading','--with-filename','--only-matching',r'"[A-Za-z_]*seed"\s*:\s*[0-9]+','reports','-g','*.json','-g','*.jsonl'],stdout=subprocess.PIPE,text=True)
used=set();overlap=[];fields=0
for line in proc.stdout:
    match=re.search(r':\s*(\d+)\s*$',line)
    if match:
        seed=int(match[1]);used.add(seed);fields+=1
        if seed in proposed:overlap.append(line.strip())
assert proc.wait() in (0,1)
# ZIP members are inspected by name and only seed arrays are decompressed.
binary=[];errors=[]
for path in sorted(Path('reports').rglob('*.npz')):
    try:
        with np.load(path,allow_pickle=False) as archive:
            keys=[k for k in archive.files if 'seed' in k.lower()]
            values=[]
            for key in keys:
                a=archive[key]
                if np.issubdtype(a.dtype,np.integer):values.extend(map(int,a.reshape(-1)))
            used.update(values)
            overlap.extend(f'{path}: binary seed {s}' for s in values if s in proposed)
            binary.append(dict(path=str(path),keys=keys,seed_values=len(values)))
    except Exception as exc:errors.append(dict(path=str(path),error=str(exc)))
audit=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),seed_fields=fields,unique_seeds=len(used),binary=binary,errors=errors,overlap=overlap,passed=not(overlap or errors),proposed=sorted(proposed),scope='All report JSON/JSONL seed fields, including ignored files, plus all NPZ seed arrays; pickled root provenance is represented by JSON gate/plan sidecars.')
write(HERE/'seed-audit.json',audit)
assert audit['passed'],(overlap,errors)
cats=catalogs();held={}
for role in ('eval','eval_ood'):
    for d in cats[role]['decks']:
        key=tuple(d['cards']);held.setdefault(key,0);held[key]+=d['frequency']
held=[dict(cards=list(d),frequency=n) for d,n in held.items()]
train=cats['train']['decks'];rng=random.Random(3420700001)
def choose(rows):return rng.choices(rows,weights=[r['frequency'] for r in rows],k=1)[0]
schedule=[]
for f,count in zip(FAMILIES,[19,19,18,18,18,18,18]):
    pool=[d for d in held if family(d['cards'])==f]
    assert pool,f
    for _ in range(count):
        i=len(schedule);own=list(choose(pool)['cards']);opponent=list(choose(train)['cards']);rng.shuffle(own);rng.shuffle(opponent)
        schedule.append(dict(pair=i,seed=BASE+1009*i,family=f,style=('balanced','pressure','defense')[i%3],planning_deck=own,opponent_deck=opponent))
assert len(schedule)==128
path=HERE/'schedule.json'
assert not path.exists(),'never overwrite a registered schedule'
write(path,dict(utc=audit['utc'],pairs=schedule,sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROLES,INDEX,CATALOG,HERE.parent/'PREREG-C56.md')},seed_audit_sha256=hashlib.sha256((HERE/'seed-audit.json').read_bytes()).hexdigest()))
print('registered',len(schedule),'pairs; historical seed fields',fields,'binary archives',len(binary))
