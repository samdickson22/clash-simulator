"""Freeze 48 fresh paired worlds before any evaluation gameplay."""
import json,random,re,subprocess,time,hashlib
from pathlib import Path
import numpy as np
H=Path(__file__).resolve().parent;R=H.parents[3]
seeds=[1967050031+1009*i for i in range(48)]
# All report paths, including ignored files. Search concrete seed literals in
# textual manifests; inspect compressed NPZ seed arrays without loading games.
args=['rg','--no-ignore','--hidden','-l','-F']
for s in seeds:args+=['-e',str(s)]
args+=['reports','-g','*.json','-g','*.jsonl','-g','*.toml','-g','*.csv','-g','*.txt','-g','*.md','-g','*.py','-g','!**/live-loop/l2/**']
r=subprocess.run(args,cwd=R,capture_output=True,text=True)
if r.returncode not in (0,1):raise RuntimeError(r.stderr)
assert not r.stdout,r.stdout
count=0;npz_fields=0
for p in (R/'reports').rglob('*.npz'):
    count+=1
    with np.load(p,allow_pickle=False) as z:
        for key in z.files:
            if 'seed' not in key.lower():continue
            values=np.asarray(z[key]);npz_fields+=values.size
            assert not np.isin(values,seeds).any(),str(p)
decks=[['HogRider','Musketeer','Cannon','Fireball','Log','IceGolem','IceSpirit','Skeletons'],
 ['Xbow','Tesla','Knight','Archers','Fireball','Log','Skeletons','ElectroSpirit'],
 ['RoyalHogs','FirespiritHut','GoblinHut','Berserker','Ghost','Fireball','Log','ElectroSpirit']]
families=['Hog 2.6','X-Bow cycle','Royal Hogs spawners'];styles=['balanced','pressure','defense']
entries=[]
for i,seed in enumerate(seeds):
 f=i//16;j=i%16;rng=random.Random(seed)
 own=list(decks[f]);enemy=list(decks[0 if f==0 else (j%3)])
 rng.shuffle(own);rng.shuffle(enemy)
 entries.append(dict(pair=i,seed=seed,family=families[f],mode='p16' if f==0 else 'c56',style=styles[(j+f)%3],decks=[enemy,own],seat=1))
(H/'seed-audit.json').write_text(json.dumps(dict(time=time.time(),proposed=seeds,text_overlap=[],npz_files=count,npz_seed_values=npz_fields,passed=True,scope='all ignored/nonignored report text manifests and NPZ seed arrays; no media content seed claim'),indent=2)+'\n')
(H/'schedule.json').write_text(json.dumps(dict(created=time.time(),matches=entries),indent=2)+'\n')
print('48 worlds prepared; no games played',flush=True)
