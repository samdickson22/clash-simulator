import bootstrap
from bootstrap import HERE,ROOT
import datetime,hashlib,importlib.util,json,random,re,subprocess
from pathlib import Path
import numpy as np

def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
worlds=[7612000001+1009*i for i in range(192)]
noise=[8612000001+1009*i for i in range(192)]
proposed={s+offset for s in worlds for offset in (0,100000,100001,100002,100003)}|{s+offset for s in noise for offset in (0,1,500,501,700,701)}
assert len(proposed)==2112
used=set();fields=0;errors=[];overlap=[]
cmd=['rg','--hidden','--no-ignore','--no-heading','--with-filename','--only-matching',r'"[A-Za-z_]*seed"\s*:\s*[0-9]+','reports','-g','*.json','-g','*.jsonl','-g','!**/search-noise-v2/**']
p=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,text=True)
for line in p.stdout:
    m=re.search(r':\s*(\d+)\s*$',line)
    if m:
        s=int(m[1]);fields+=1;used.add(s)
        if s in proposed:overlap.append(line.strip())
assert p.wait() in (0,1)
archives=0;metadata=0;unavailable=[]
for p in sorted((ROOT/'reports').rglob('*.npz')):
    if HERE in p.parents:continue
    if p.is_symlink() and not p.exists():
        unavailable.append(dict(path=str(p),target=str(p.readlink())));continue
    try:
        with np.load(p,allow_pickle=False) as z:
            archives+=1;found=set()
            for key in z.files:
                found.update(int(s) for s in re.findall(r'seed[_-]?(\d+)',key,re.I))
                if not any(t in key.lower() for t in ('meta','config','seed','json')):continue
                a=z[key]
                if a.dtype.kind in ('U','S'):
                    for value in a.reshape(-1):
                        if isinstance(value,bytes):value=value.decode()
                        found.update(int(s) for s in re.findall(r'"[A-Za-z_]*seed"\s*:\s*(\d+)',str(value)))
                elif 'seed' in key.lower() and a.dtype.kind in ('i','u'):found.update(map(int,a.reshape(-1)))
            used.update(found);metadata+=len(found);overlap.extend(f'{p}: {s}' for s in found&proposed)
    except Exception as e:errors.append([str(p),str(e)])
pattern=r'(?<!\d)(?:'+'|'.join(map(str,sorted(proposed)))+r')(?!\d)'
cmd=['rg','--pcre2','--hidden','--no-ignore','--no-heading','--with-filename','--only-matching',pattern,'reports']
for ext in ('json','jsonl','log','md','txt','toml','yaml','csv','tsv','py','sh'):cmd+=['-g','*.'+ext]
cmd+=['-g','!**/search-noise-v2/**']
p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);assert p.returncode in (0,1),p.stderr;overlap+=p.stdout.splitlines()
audit=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),seed_fields=fields,unique_seeds=len(used),npz_archives=archives,metadata_seeds=metadata,unavailable_archives=unavailable,errors=errors,overlap=overlap,passed=not errors and not overlap,proposed=sorted(proposed))
write(HERE/'seed-audit.json',audit);assert audit['passed'],(errors,overlap)
path=ROOT/'reports/strategy_council_20260928/engine-speed/stage5/decks.py'
spec=importlib.util.spec_from_file_location('source_decks',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
cats=m.catalogs();held={}
for role in ('eval','eval_ood'):
    for d in cats[role]['decks']:held[tuple(d['cards'])]=held.get(tuple(d['cards']),0)+d['frequency']
supported={tuple(sorted(d['cards'])) for d in cats['train']['decks']}
held=[dict(cards=list(d),frequency=n) for d,n in held.items() if tuple(sorted(d)) in supported]
rng=random.Random(7611100001)
def choose(rows):return rng.choices(rows,weights=[r['frequency'] for r in rows],k=1)[0]
schedule=[]
for mode in ('head-to-head','scripts'):
    for family,count in zip(['Hog 2.6','Hog EQ/Firecracker/MM','Royal Hogs/Furnace','X-Bow','bait','Goblinstein','AQ'],([10,9,9,9,9,9,9] if mode=='head-to-head' else [20,18,18,18,18,18,18])):
        pool=[d for d in held if m.family(d['cards'])==family];assert pool
        for _ in range(count):
            i=len(schedule);a=list(choose(pool)['cards']);b=list(choose(cats['train']['decks'])['cards']);rng.shuffle(a);rng.shuffle(b)
            schedule.append(dict(pair=i,mode=mode,seed=worlds[i],noise_seed=noise[i],family=family,style=('balanced','pressure','defense')[i%3],planning_deck=a,opponent_deck=b))
assert len(schedule)==192
sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (m.ROLES,m.INDEX,m.CATALOG,path,HERE/'PREREG.md',HERE/'noise-model.json')}
assert not (HERE/'schedule.json').exists()
write(HERE/'schedule.json',dict(utc=audit['utc'],pairs=schedule,sources=sources,seed_audit_sha256=hashlib.sha256((HERE/'seed-audit.json').read_bytes()).hexdigest()))
print('registered',len(schedule),'pairs;',fields,'seed fields;',archives,'archives',flush=True)
