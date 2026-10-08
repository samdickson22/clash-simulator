import bootstrap
from bootstrap import HERE
import argparse,json
from evaluate import Resources,game,write
from dev_trace import schedule
from derived_public_state import DerivedPublicState
from cells import CELLS
ap=argparse.ArgumentParser();ap.add_argument('--index',type=int,required=True);args=ap.parse_args()
r=Resources();prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text());r.initial_belief=DerivedPublicState(prior,r.costs)
s=schedule()[0];ep=dict(pair=-1,seed=s['seed'],noise_seed=s['noise_seed'],planning_deck=s['decks'][0],opponent_deck=s['decks'][1],mode='scripts',family=s['family'],style=s['style'])
row=game(r,prior,ep,args.index%2,list(CELLS)[args.index],trace_enabled=False)
safe={k:row[k] for k in ('variant','terminal','ticks','elapsed','cpu_seconds','timing','host','perception','action_sha256','action_count')}
write(HERE/f'pilot-{args.index}.json',safe);print(json.dumps(safe),flush=True)
