"""Frequency order, fixed catalogue, support filter, <=4/8 R1 and guard overlap."""
import argparse,json
from pathlib import Path
from common import plan,HERE,ROOT,read,write,sha,utc
L2=[['HogRider','Musketeer','Cannon','Fireball','Log','IceGolem','IceSpirit','Skeletons'],['Xbow','Tesla','Knight','Archers','Fireball','Log','Skeletons','ElectroSpirit'],['RoyalHogs','FirespiritHut','GoblinHut','Berserker','Ghost','Fireball','Log','ElectroSpirit']]

def select(catalogue,primary,support):
 training=primary+L2;chosen=[];skipped=[]
 # Canonical lexical tie-break is fixed before any card-support results.
 ordered=sorted(catalogue['decks'],key=lambda d:(-d['frequency'],tuple(sorted(d['cards']))))
 for d in ordered:
  cards=d['cards'];assert len(cards)==len(set(cards))==8
  r1=max(len(set(cards)&set(t)) for t in training)
  guard=max((len(set(cards)&set(t['cards'])) for t in chosen),default=0)
  if r1>4 or guard>4:continue
  invalid=[c for c in cards if not support[c]['supported']]
  if invalid:skipped.append(dict(cards=cards,frequency=d['frequency'],unsupported=invalid));continue
  chosen.append(dict(cards=cards,frequency=d['frequency'],r1_max_shared=r1,earlier_guard_max_shared=guard))
  if len(chosen)==3:break
 assert len(chosen)==3,'fewer than three supported held-out decks'
 return chosen,skipped

def main():
 import run
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=HERE/'guard-decks.json');a=p.parse_args()
 cfg=plan();path=ROOT/'reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json';assert sha(path)==cfg['catalogue_sha256']
 native=run.initialize();assert sha(native)==cfg['source_reference']['native_sha256']
 from clasher.analysis.loss_review.metrics import archetype
 catalogue=read(path);assert len(catalogue['decks'])==2925
 primary=[max((d for d in catalogue['decks'] if archetype(d['cards'])==f),key=lambda d:d['frequency'])['cards'] for f in ('bridge_wincon','siege','beatdown','bait','chip')]
 import importlib.util
 source=HERE/'inherited/r1/emitter.py'
 expected=read(HERE/'provenance.json')['r1_emitter']['sha256'];assert sha(source)==expected
 spec=importlib.util.spec_from_file_location('_t1_frozen_r1_emitter',source)
 emitter=importlib.util.module_from_spec(spec);spec.loader.exec_module(emitter)
 emitter.PRIOR=catalogue
 assert emitter.decks()==primary+L2,'R1 emitter training-deck binding'
 support={}
 for c in sorted({c for d in catalogue['decks'] for c in d['cards']}):
  tok=run.R.builder.token_id(c,namespace='card_action')
  native_ok=c in run.R.config['cards'];v1_ok=1<tok<len(run.POLICY.costs) and float(run.POLICY.costs[tok])>0
  s_ok=1<tok<len(run.STUDENT.costs) and float(run.STUDENT.costs[tok])>0
  support[c]=dict(token=int(tok),native=native_ok,v1_vocab=v1_ok,R3a_vocab=s_ok,supported=native_ok and v1_ok and s_ok)
 guard,skipped=select(catalogue,primary,support)
 # Native execution and public observation for every selected guard card; no unknown fallbacks.
 from stage2_matches import battle
 from fair_player import observe
 from differential import Position
 import numpy as np
 records=[]
 for c in sorted({c for d in guard for c in d['cards']}):
  deck=[c]+[x for x in L2[0] if x!=c][:7]
  b=battle(dict(seed=880601,decks=[deck,L2[0]]),run.R.builder.loader)
  b.players[0].elixir=10.;assert b.deploy_card(0,c,Position(4.5,13.5)) is not False
  for _ in range(20):b.step()
  info=observe(b,run.R.builder,0,[]);p=b.players[1]
  root=run.R.root(info,dict(elixir=p.elixir,hand=list(p.hand),cycle=list(p.cycle_queue),refill=p.next_card_refill_cooldown_ms),np.random.default_rng(880601))
  run.R.native.rollout_e1(root,0,2304,'balanced',27,27,20,10,1.,1e6)
  records.append(dict(card=c,token=support[c]['token'],public_native_rollout_pass=True))
 write(a.out,dict(utc=utc(),catalogue_sha256=sha(path),catalogue_decks=2925,selector_sha256=sha(__file__),primary=primary,l2=L2,r1_training_deck_slots=primary+L2,distinct_training_decks=len({tuple(sorted(d)) for d in primary+L2}),guard=guard,skipped_unsupported=skipped,support={c:support[c] for d in guard for c in d['cards']},native_execution=records,support_pass=True))
 print(json.dumps(dict(guard_decks=len(guard),supported_cards=len(records),unsupported_skips=len(skipped))))
if __name__=='__main__':main()
