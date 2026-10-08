import bootstrap
from bootstrap import HERE
import argparse,importlib.util,json
from evaluate import Resources,game,write
from derived_public_state import DerivedPublicState
from cells import CELLS
ap=argparse.ArgumentParser();ap.add_argument('--index',type=int,required=True);args=ap.parse_args()
r=Resources();prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text());r.initial_belief=DerivedPublicState(prior,r.costs)
deck=['HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log']
def episode(i):return dict(pair=-1,seed=9750800001+1009*i,noise_seed=9850800001+1009*i,planning_deck=deck,opponent_deck=deck[::-1],mode='scripts',family='Hog 2.6',style='balanced')
if args.index<3:
 spec=importlib.util.spec_from_file_location('s2_reference_player',HERE.parent/'search-noise-s2/player.py');ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
 import evaluate
 original=evaluate.Player;out=[]
 for cell in ('Full','R-derived'):
  evaluate.Player=original;a=game(r,prior,episode(args.index),args.index%2,cell,trace_enabled=False)
  evaluate.Player=ref.Player;b=game(r,prior,episode(args.index),args.index%2,cell,trace_enabled=False)
  for key in ('action_sha256','action_count','ticks'):assert a[key]==b[key],(cell,key)
  out.append(dict(cell=cell,passed=True,action_sha256=a['action_sha256'],action_count=a['action_count'],ticks=a['ticks'],cpu_seconds=a['cpu_seconds']+b['cpu_seconds']))
 write(HERE/f'equivalence-{args.index}.json',dict(passed=True,index=args.index,cells=out));print('equivalence passed',flush=True)
else:
 i=args.index-3;row=game(r,prior,episode(0),i%2,list(CELLS)[i],trace_enabled=False)
 safe={k:row[k] for k in ('variant','terminal','ticks','elapsed','cpu_seconds','timing','host','perception','action_sha256','action_count')}
 write(HERE/f'pilot-{i}.json',safe);print('pilot complete',flush=True)
