"""Fresh registered banks for MAX play and current-account spending context."""
import argparse,json,os,random
from sam_common import ROOT,OLD,DECKS,POLICIES,sha,utc,dump,record
def prepare(stage):
 from bot.fullpool.cards import C56,engine_name
 from bot.levels.profile import clamp,RARE_OFFSET
 assert set(c for d in DECKS.values() for c in d)<=set(C56)
 source=json.loads((OLD/'upgrade-source-gamedata.json').read_text())
 table={r['name']:r for r in source['items']['rarities']}
 for r in ('Common','Rare','Epic','Legendary','Champion'):
  assert int(table[r]['relativeLevel'])+int(table[r]['levelCount'])==16
 rarity={engine_name(r['name'],strict=False):str(r['rarity']).lower() for r in source['items']['spells']}
 current=None
 if stage in ('current','upgrades'):
  current=json.loads((ROOT/'collection-current.json').read_text())
  levels={n:{c:int(current[c]['level']) for c in deck} for n,deck in DECKS.items()}
 else:levels={n:{c:16 for c in deck} for n,deck in DECKS.items()}
 decks=DECKS
 if stage=='upgrades':
  plans=json.loads((ROOT/'upgrade-variants.json').read_text())
  decks={n:DECKS['sam'] for n in plans['plans']}
  levels={n:p['levels'] for n,p in plans['plans'].items()}
 count=60 if stage=='upgrades' else 100
 population=[json.loads(s) for s in (OLD/'opponent-decks.jsonl').read_text().splitlines()]
 assert len(population)==91
 old=json.loads((OLD/'fullpool/manifest.json').read_text());config=old['player_config']
 entropy=os.urandom(16).hex();rng=random.Random(int(entropy,16));cases=[]
 prior_levels,prior_weights=zip(*old['opponent_common_prior'])
 for oi,opponent in enumerate(POLICIES):
  for i in range(count):
   seed=rng.randrange(1<<48);crng=random.Random(seed);source_index=crng.randrange(91)
   deck=[engine_name(c) for c in population[source_index]['opp_deck']];crng.shuffle(deck)
   order=list(range(8));crng.shuffle(order);lrng=random.Random(seed^0x1E7E1)
   opp_levels={c:16 for c in deck} if stage=='max' else {c:clamp(rarity[c],lrng.choices(prior_levels,weights=prior_weights)[0]-RARE_OFFSET.get(rarity[c],1)) for c in deck}
   cases.append(dict(id=f'{stage}-{oi}-{i:04d}',opponent=opponent,index=i,seed=seed,seat=i%2,source_index=source_index,opponent_deck=deck,opponent_levels=opp_levels,own_permutation=order))
 dispatch=list(range(len(cases)));rng.shuffle(dispatch)
 used=set()
 for p in [OLD/'fullpool/validation/bank.json']+[ROOT/s/'validation/bank.json' for s in ('upgrades','max','current') if s!=stage]:
  if p.exists():used.update(c['seed'] for c in json.loads(p.read_text())['cases'])
 assert not used & {c['seed'] for c in cases}
 meta=dict(created_utc=utc(),scenario='Sam follow-up '+stage,candidates=decks,candidate_plans={n:dict(levels=v) for n,v in levels.items()},
  tower_level=16 if stage=='max' else 7,player_config=config,players=config['players'],opponents=POLICIES,
  card_scope='three specified C56 decks; actual Battle Log opponent decks',
  original_manifest_sha256=sha(OLD/'fullpool/manifest.json'),population_sha256=sha(OLD/'opponent-decks.jsonl'),
  collection_sha256=sha(ROOT/'collection-current.json') if current else None,
  gamedata_sha256=sha(OLD/'upgrade-source-gamedata.json'),runtime_pin='live16402b-r3',
  source_commit=old['source_commit'],simulator=old['simulator'],opponent_common_prior=old['opponent_common_prior'],
  planner='unchanged deployed all-L11/root/belief handling; MAX applies to simulator truth',
  inference='information only; 20k paired within-policy bootstrap, pointwise 95% CIs; no selection/deployment',
  helper_sha256={p.name:sha(p) for p in ROOT.glob('sam_*.py')})
 dump(ROOT/stage/'manifest.json',meta,True)
 bank=dict(stage='validation',scenario=meta['scenario'],created_utc=utc(),entropy_hex=entropy,cases=cases,cases_per_policy=100,
  candidates=list(decks),players=config['players'],dispatch_order=dispatch,candidate_levels=levels,own_tower=meta['tower_level'],opponent_tower=meta['tower_level'],manifest_sha256=sha(ROOT/stage/'manifest.json'))
 bank['cases_per_policy']=count
 dump(ROOT/stage/'validation/bank.json',bank,True);record(f'Registered {stage} bank before games: {sha(ROOT/stage/"validation/bank.json")},{len(cases)}cases/{len(cases)*len(decks)*2}games.')
 print(stage,bank['created_utc'],sha(ROOT/stage/'validation/bank.json'))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',choices=('upgrades','max','current'));prepare(p.parse_args().stage)
