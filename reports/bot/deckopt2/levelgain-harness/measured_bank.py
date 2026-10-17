"""Measured level-only redraw, preserving the registered paired case bank."""
import collections,json,random
from sam_common import ROOT,OLD,utc,sha,dump,record

def register():
 from bot.fullpool.cards import engine_name
 from bot.levels.profile import FLOOR
 path=ROOT/'input-opponent-decks-20261017-1850.jsonl'
 raw=[json.loads(s) for s in path.read_text().splitlines()]
 assert len(raw)==14
 gd=json.loads((OLD/'upgrade-source-gamedata.json').read_text())
 rarity={engine_name(r['name'],strict=False):str(r['rarity']).lower() for r in gd['items']['spells']}
 counts=collections.defaultdict(collections.Counter);global_counts=collections.Counter();kings=collections.Counter();nulls=[]
 for i,row in enumerate(raw):
  kings[int(row['opp_king_level'])]+=1
  assert len(row['opp_deck'])==len(row['opp_levels'])==8
  for slot,(c,l) in enumerate(zip(row['opp_deck'],row['opp_levels'])):
   l=int(l);assert 1<=l<=16;global_counts[l]+=1
   if c is None:nulls.append(dict(row=i,slot=slot,level=l));continue
   counts[rarity[engine_name(c)]][l]+=1
 assert sum(global_counts.values())==112 and len(nulls)==3
 oldmeta=json.loads((ROOT/'shifted/manifest.json').read_text());base=json.loads((ROOT/'base-bank.json').read_text())
 meta=dict(oldmeta);meta['created_utc']=utc();meta['scenario']='Sam level gain — 1,850 Battle Log prior'
 plans=dict(meta['candidate_plans']);own=plans['baseline']['levels']
 for card in ('Valkyrie','Fireball'):plans[card.lower()+'-plus1']=dict(levels={c:l+int(c==card) for c,l in own.items()})
 meta['candidate_plans']=plans;meta['candidates']={n:oldmeta['candidates']['baseline'] for n in plans}
 meta['helper_sha256']={**meta['helper_sha256'],**{n:sha(ROOT/n) for n in ('measured_bank.py','extended_queue.py','extended_worker.py')}}
 meta['prior']=dict(label='1,850 Battle Log prior',source_sha256=sha(path),rows=14,identified_slots=109,null_slots=nulls,all112_level_counts=dict(global_counts),level_counts={k:dict(v) for k,v in counts.items()},opponent_king_counts=dict(kings),trophy_range=[min(r['opp_trophies'] for r in raw),max(r['opp_trophies'] for r in raw)],mean_trophies=sum(r['opp_trophies'] for r in raw)/14,draw='independent empirical rarity-specific card levels and independent empirical King',missing_rarity_fallback='all112 displayed levels pooled, clamped to rarity floor; unknown identities never inferred',null_cards='keep population fallback; no identity/variant inference',decks='original91 true decks and registered seeds unchanged; new14rows supply levels/towers only')
 cases=[]
 for c in base['cases']:
  rng=random.Random(c['seed']^0x1E7E1);levels={}
  for card in c['opponent_deck']:
   rar=rarity[card];dist=counts.get(rar,global_counts);keys,weights=zip(*sorted(dist.items()));levels[card]=max(FLOOR.get(rar,1),int(rng.choices(keys,weights=weights)[0]))
  keys,weights=zip(*sorted(kings.items()));king=random.Random(c['seed']^0x701E).choices(keys,weights=weights)[0]
  cases.append(dict(c,opponent_levels=levels,opponent_tower_level=king))
 stage='battlelog1850';dump(ROOT/stage/'manifest.json',meta,True)
 bank=dict(stage='validation',scenario=meta['scenario'],created_utc=utc(),cases=cases,cases_per_policy=100,candidates=list(plans),players=meta['players'],dispatch_order=base['dispatch_order'],manifest_sha256=sha(ROOT/stage/'manifest.json'),base_bank_sha256=sha(ROOT/'base-bank.json'))
 dump(ROOT/stage/'validation/bank.json',bank,True)
 record(f'Registered measured1850 eight arms:1600games; bankSHA {sha(ROOT/stage/"validation/bank.json")}; original shifted bank untouched.')
 print(json.dumps(meta['prior']));print(sha(ROOT/stage/'validation/bank.json'))
if __name__=='__main__':register()
