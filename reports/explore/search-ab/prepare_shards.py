"""Preserve completed home games and split the fixed paired seed schedule."""
import hashlib,json,shutil
from pathlib import Path
root=Path(__file__).resolve().parent
master=json.loads((root/'primary-127x04/schedule.json').read_text());selected=master['selected_decks'];ex=root/'exclusions.json'
existing={}
for name in ['primary-127x04','primary-127x08','primary-final300-127x04']:
 for p in (root/name/'games').glob('*.json'):
  r=json.loads(p.read_text());key=r['identity']
  if key in existing:raise ValueError('duplicated home game')
  existing[key]=p
manifest=[]
for offset in range(0,2000,125):
 out=root/'shards'/f'p{offset:04d}';(out/'games').mkdir(parents=True,exist_ok=True);cases=[];seeds=set();kept=0
 for pair in range(offset,offset+125):
  seed=2**48+10000+pair
  seeds.update(seed+off for off in (0,100000,100001,100002))
  for arm in ['0','C','R','CR']:
   cases.append((pair,seed,27,selected[pair%5],selected[(pair//5)%5],('balanced','pressure','defense')[(pair//25)%3],arm))
   key=f'sim-{pair:04d}-d27-{arm}'
   if key in existing:
    shutil.copy2(existing[key],out/'games'/f'{key}.json');kept+=1
 schedule=dict(cases=cases,seed_exclusions_sha256=hashlib.sha256(ex.read_bytes()).hexdigest(),checked_seeds=sorted(seeds),intersections=[],purpose='exploration only',selected_decks=selected)
 (out/'schedule.json').write_text(json.dumps(schedule,separators=(',',':'))+'\n')
 manifest.append(dict(name=out.name,offset=offset,pairs=125,retained_home_games=kept,requested_games=500))
(root/'shards.json').write_text(json.dumps(dict(paired_seeds=2000,retained_home_games=len(existing),shards=manifest),indent=2)+'\n')
print(json.dumps(dict(shards=len(manifest),retained_home_games=len(existing))))
