"""Same fifty reconstructions, with explicit per-card rarity-relative levels."""
import gzip,json
from pathlib import Path
from study import OUT,ROOT,IDS,TOWERS,base_slug,config_for,run_one,request,PORT
from read_native_public_levels import read_levels
rows=[json.loads(l) for l in gzip.open(OUT/'sample50.jsonl.gz','rt')]
baselines={r['index']:r for r in map(json.loads,open(OUT/'results-terminal-50.jsonl'))}
spells={s['id']:s for s in json.load(open(ROOT/'gamedata.json'))['items']['spells']}
baselevel={'Common':1,'Rare':3,'Epic':6,'Legendary':9,'Champion':11}
with (OUT/'levelled-order.jsonl').open('w') as f:
 for row in rows:
  p=row['payload'];c=config_for(p);base=baselines[row['index']];c['battle']['lvlcap']=0;c['battle']['cardlvlmin']=0
  for owner,side in enumerate(['team','opponent']):
   player=p['battle'][side]['players'][0];prior=base['initial_observe']['players'][owner]
   permutation=[v['deckSlot'] for v in prior['hand']+prior['cycle']]
   entries={v['d']:v for v in c['battle'][f'deck{owner}']['sp']};order=[]
   for v in player['deck']:
    cid=IDS[base_slug(v['card_key'])[0]];entries[cid]['l']=v['level']-baselevel[spells[cid]['rarity']]
   support=c['battle'][f'deck{owner}']['sc'][0];support['l']=player['tower_card']['level']-baselevel[spells[support['d']]['rarity']]
   for e in p['events']:
    if e['side']==side and e['kind']=='play_card':
     cid=IDS[base_slug(e['card_key'])[0]]
     if cid not in order and cid in entries:order.append(cid)
   order += [cid for cid in entries if cid not in order];dest=[None]*8
   for slot,cid in zip(permutation,order):dest[slot]=entries[cid]
   c['battle'][f'deck{owner}']['sp']=dest
  r=run_one(row,config_override=c)
  r['native_config']=c
  if row['index'] in [0,526,6]:
   r['verified_final_levels']=read_levels(Path.home()/'.cache/clasher-native-reference/android-sdk/platform-tools/adb',port=PORT,serial='emulator-5584',batched=True,persistent=True)
  f.write(json.dumps(r)+'\n');f.flush();print(row['index'],r.get('failure'),sum(a['state']=='failed' for a in r.get('action_receipts',[])),flush=True)
