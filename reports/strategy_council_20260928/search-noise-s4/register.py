import bootstrap
from bootstrap import HERE,ROOT
import datetime,hashlib,importlib.util,json,random,re,subprocess
from pathlib import Path
import numpy as np

def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
worlds=[9752000001+1009*i for i in range(128)]
noise=[9852000001+1009*i for i in range(128)]
from seed_audit import audit as run_audit
audit=json.loads((HERE/'seed-audit-127x04.json').read_text())
write(HERE/'seed-audit.json',audit);assert audit['passed'],(audit['errors'],audit['overlap'])
path=ROOT/'reports/strategy_council_20260928/engine-speed/stage5/decks.py'
spec=importlib.util.spec_from_file_location('source_decks',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
cats=m.catalogs();held={}
for role in ('eval','eval_ood'):
    for d in cats[role]['decks']:held[tuple(d['cards'])]=held.get(tuple(d['cards']),0)+d['frequency']
supported={tuple(sorted(d['cards'])) for d in cats['train']['decks']}
held=[dict(cards=list(d),frequency=n) for d,n in held.items() if tuple(sorted(d)) in supported]
rng=random.Random(9751100001)
def choose(rows):return rng.choices(rows,weights=[r['frequency'] for r in rows],k=1)[0]
schedule=[]
for mode in ('scripts',):
    for family,count in zip(['Hog 2.6','Hog EQ/Firecracker/MM','Royal Hogs/Furnace','X-Bow','bait','Goblinstein','AQ'],([10,9,9,9,9,9,9] if mode=='head-to-head' else [20,18,18,18,18,18,18])):
        pool=[d for d in held if m.family(d['cards'])==family];assert pool
        for _ in range(count):
            i=len(schedule);a=list(choose(pool)['cards']);b=list(choose(cats['train']['decks'])['cards']);rng.shuffle(a);rng.shuffle(b)
            schedule.append(dict(pair=i,mode=mode,seed=worlds[i],noise_seed=noise[i],family=family,style=('balanced','pressure','defense')[i%3],planning_deck=a,opponent_deck=b))
assert len(schedule)==128
sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (m.ROLES,m.INDEX,m.CATALOG,path,HERE/'PREREG.md',HERE/'noise-model.json')}
assert not (HERE/'schedule.json').exists()
write(HERE/'schedule.json',dict(utc=audit['utc'],pairs=schedule,sources=sources,seed_audit_sha256=hashlib.sha256((HERE/'seed-audit.json').read_bytes()).hexdigest()))
print('registered',len(schedule),'pairs;',audit['seed_fields'],'seed fields;',audit['npz_archives'],'archives',flush=True)
