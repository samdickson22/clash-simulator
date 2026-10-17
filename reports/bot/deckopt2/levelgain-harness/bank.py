"""Six level arms, fresh paired seeds; later change opponent prior only."""
import argparse,collections,json,math,os,random
from sam_common import ROOT,OLD,DECKS,POLICIES,utc,sha,dump,record
def register(stage,rows_path=None):
 from bot.fullpool.cards import engine_name
 from bot.levels.profile import FLOOR,RARE_OFFSET
 gd=json.loads((OLD/'upgrade-source-gamedata.json').read_text())
 rarity={engine_name(r['name'],strict=False):str(r['rarity']).lower() for r in gd['items']['spells']}
 pop=[json.loads(s) for s in (OLD/'opponent-decks.jsonl').read_text().splitlines()]
 assert len(pop)==91
 deck=DECKS['sam'];collection=json.loads((ROOT/'input-collection.json').read_text())
 own={c:int(collection[c]['level']) for c in deck}
 plans={'baseline':dict(levels=own),'all-plus1':dict(levels={c:l+1 for c,l in own.items()})}
 for card in ('Giant','MiniPekka','Cannon','Bats'):plans[card.lower()+'-plus1']=dict(levels={c:l+int(c==card) for c,l in own.items()})
 path=ROOT/'base-bank.json'
 if not path.exists():
  assert stage=='shifted';entropy=os.urandom(16).hex();rng=random.Random(int(entropy,16));cases=[]
  used=set()
  for d in (ROOT.parent/'bot-deckopt2-sam',OLD):
   for p in d.glob('*/validation/bank.json'):
    used.update(c['seed'] for c in json.loads(p.read_text())['cases'])
  for oi,policy in enumerate(POLICIES):
   for i in range(100):
    seed=rng.randrange(1<<48)
    assert seed not in used;used.add(seed);r=random.Random(seed);index=r.randrange(91)
    opp=[engine_name(c) for c in pop[index]['opp_deck']];r.shuffle(opp);order=list(range(8));r.shuffle(order)
    cases.append(dict(id=f'levelgain-{oi}-{i:04d}',seed=seed,index=i,seat=i%2,opponent=policy,source_index=index,opponent_deck=opp,own_permutation=order))
  dispatch=list(range(len(cases)));rng.shuffle(dispatch)
  dump(path,dict(created_utc=utc(),entropy_hex=entropy,cases=cases,dispatch_order=dispatch),True)
 base=json.loads(path.read_text());prior={};king_counts=collections.Counter();counts={}
 if stage=='shifted':
  values=[]
  for row in pop:
   for c,l in zip(row['opp_deck'],row['opp_levels']):
    if l is not None and rarity[engine_name(c)]=='common':values.append((float(row['opp_trophies']),int(l)))
  mx=sum(x for x,y in values)/len(values);my=sum(y for x,y in values)/len(values)
  slope=sum((x-mx)*(y-my) for x,y in values)/sum((x-mx)**2 for x,y in values)
  shift=slope*(1850-mx);counts['common']=collections.Counter(y for x,y in values);king_counts[8]=1
  prior=dict(label='shifted prior (provisional extrapolation)',observations=len(values),trophy_range=[min(x for x,y in values),max(x for x,y in values)],mean_trophies=mx,mean_common_level=my,slope_per_100_trophies=100*slope,target_trophies=1850,mean_shifted_common=my+shift,common_shift=shift,rounding='stochastic integer rounding of shift per card',opponent_king='8 assumed, round(mean shifted common)-1; our King7',population_sha256=sha(OLD/'opponent-decks.jsonl'))
 else:
  assert rows_path and rows_path.exists();fresh=[json.loads(s) for s in rows_path.read_text().splitlines() if s.strip()];assert fresh
  used_keys=collections.Counter()
  for row in fresh:
   levels=row['opp_levels'];levels=[levels.get(c) for c in row['opp_deck']] if isinstance(levels,dict) else levels
   assert len(levels)==len(row['opp_deck'])
   for c,l in zip(row['opp_deck'],levels):
    if l is None:continue
    l=int(l);assert 1<=l<=16;counts.setdefault(rarity[engine_name(c)],collections.Counter())[l]+=1
   for key in ('opp_king_level','opponent_king_level','opp_king','king_level'):
    if row.get(key) is not None:
     v=int(row[key]);assert 1<=v<=16;king_counts[v]+=1;used_keys[key]+=1;break
  assert counts.get('common'),'No observed common card levels; inspect source rather than guess'
  assert king_counts,'No opponent King field recognized; inspect schema before freezing'
  shift=0
  prior=dict(label='1,850 Battle Log prior',source=str(rows_path),source_sha256=sha(rows_path),rows=len(fresh),level_counts={k:dict(v) for k,v in counts.items()},opponent_king_counts=dict(king_counts),king_source_keys=dict(used_keys),missing_rarity_fallback='independent common draw minus1, clamped to rarity floor',decks='unchanged original91 true decks; new file used for level/tower population only')
 cases=[]
 for c in base['cases']:
  r=random.Random(c['seed']^0x1E7E1);levels={}
  for card in c['opponent_deck']:
   rar=rarity[card];dist=counts.get(rar,counts['common']);keys,weights=zip(*sorted(dist.items()));v=r.choices(keys,weights=weights)[0]
   if stage=='shifted':v+=math.floor(shift)+int(r.random()<shift-math.floor(shift))
   if rar not in counts:v-=RARE_OFFSET.get(rar,1)
   levels[card]=max(FLOOR.get(rar,1),min(int(v),16))
  kr=random.Random(c['seed']^0x701E);keys,weights=zip(*sorted(king_counts.items()));king=kr.choices(keys,weights=weights)[0]
  cases.append(dict(c,opponent_levels=levels,opponent_tower_level=king))
 config=json.loads((OLD/'fullpool/player-config.json').read_text());config['players']=[p for p in config['players'] if p.endswith('-res')]
 original=json.loads((OLD/'fullpool/manifest.json').read_text())
 meta=dict(created_utc=utc(),scenario='Sam level gain — '+prior['label'],candidates={n:deck for n in plans},candidate_plans=plans,tower_level=7,player_config=config,players=config['players'],opponents=POLICIES,prior=prior,collection_sha256=sha(ROOT/'input-collection.json'),source_commit=original['source_commit'],original_manifest_sha256=sha(OLD/'fullpool/manifest.json'),base_bank_sha256=sha(path),helper_sha256={n:sha(ROOT/n) for n in ('sam_common.py','sam_worker.py','sam_queue.py','bank.py')},arms='hypothetical truth levels; not a spend plan; all-plus1 keeps our King7',card_scope='Sam C56 deck; true historical Battle Log opponent decks')
 dump(ROOT/stage/'manifest.json',meta,True)
 bank=dict(stage='validation',scenario=meta['scenario'],created_utc=utc(),cases=cases,cases_per_policy=100,candidates=list(plans),players=config['players'],dispatch_order=base['dispatch_order'],manifest_sha256=sha(ROOT/stage/'manifest.json'),base_bank_sha256=sha(path))
 dump(ROOT/stage/'validation/bank.json',bank,True);record(f'Registered {stage}: {len(cases)} cases, {len(cases)*len(plans)} games; bank SHA {sha(ROOT/stage/"validation/bank.json")}.')
 print(json.dumps(prior));print(stage,sha(ROOT/stage/'validation/bank.json'))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',choices=('shifted','battlelog1850'));p.add_argument('--rows',type=__import__('pathlib').Path);a=p.parse_args();register(a.stage,a.rows)
