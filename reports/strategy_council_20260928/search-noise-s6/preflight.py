"""Full terminal action equivalence and pilots; no outcomes retained."""
import bootstrap
from bootstrap import HERE
import argparse,importlib.util,json
from evaluate import Resources,game,write
from derived_public_state import DerivedPublicState
from cells import CELLS
ap=argparse.ArgumentParser();ap.add_argument('--index',type=int,required=True);args=ap.parse_args()
for host in ('127x01','127x04'):assert json.loads((HERE/f'seed-audit-{host}.json').read_text())['passed']
r=Resources();prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text());r.initial_belief=DerivedPublicState(prior,r.costs)
deck=['HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log']
def episode(i):return dict(pair=-1,seed=9780800001+1009*i,noise_seed=9880800001+1009*i,planning_deck=deck,opponent_deck=deck[::-1],mode='scripts',family='Hog 2.6',style='balanced')
if args.index<3:
    import evaluate
    original=evaluate.Player
    a=game(r,prior,episode(args.index),args.index%2,'clean-d0',trace_enabled=False)
    CELLS['clean-d0']['delay_aware']=True
    b=game(r,prior,episode(args.index),args.index%2,'clean-d0',trace_enabled=False)
    CELLS['clean-d0']['delay_aware']=False
    spec=importlib.util.spec_from_file_location('s5_reference_player',HERE.parent/'search-noise-s5/player.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    class Reference(module.Player):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw)
            from delay import CommandChannel
            self.channel=CommandChannel(0)
    evaluate.Player=Reference
    c=game(r,prior,episode(args.index),args.index%2,'clean-d0',trace_enabled=False)
    evaluate.Player=original
    assert a['terminal'] and b['terminal'] and c['terminal']
    for key in ('action_sha256','action_count','ticks'):assert a[key]==b[key]==c[key],key
    write(HERE/f'equivalence-{args.index}.json',dict(passed=True,seed=episode(args.index)['seed'],action_sha256=a['action_sha256'],action_count=a['action_count'],ticks=a['ticks'],cpu_seconds=sum(x['cpu_seconds'] for x in (a,b,c)),original_player_b=True))
    print('d0 aware/unaware/original Player B equivalence passed',flush=True)
else:
    i=args.index-3;row=game(r,prior,episode(0),i%2,list(CELLS)[i],trace_enabled=False)
    safe={k:row[k] for k in ('variant','terminal','ticks','elapsed','cpu_seconds','timing','host','perception','action_sha256','action_count','command_channel')}
    assert safe['terminal'];write(HERE/f'pilot-{i}.json',safe);print('pilot complete',flush=True)
