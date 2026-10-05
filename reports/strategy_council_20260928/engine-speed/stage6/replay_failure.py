"""Retain the first mixed ranged failure and its actual phase transitions."""
import argparse
import hashlib
import json
from pathlib import Path

import cloudpickle
import clasher_core
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
from diagnostics import detail, phase_step
from differential import Position, config, snapshot, battle_digest
from stage2 import fingerprint
from stage2_matches import battle

folder=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--receipt',type=Path,required=True);parser.add_argument('--case',required=True);parser.add_argument('--prefix',required=True)
args=parser.parse_args()
row=json.loads(args.receipt.read_text())['results'][args.case]
cfg=config(tuple(dict.fromkeys(c for deck in row['episode']['decks'] for c in deck)))
b=battle(row['episode'],ContractV5ObservationBuilder().loader)
r=clasher_core.BattleState(snapshot(b,cfg));actions=iter(row['actions']);action=next(actions,None)
target_tick=row['python']['tick']-(row['kind']!='action')
while b.tick<target_tick:
    while action is not None and action[0]==b.tick:
        tick,seat,_,name,x,y,accepted=action
        assert b.deploy_card(seat,name,Position(x,y))==accepted
        assert r.apply_action(seat,name,x,y)==accepted
        action=next(actions,None)
    b.step();r.step();assert battle_digest(b)==r.digest(),b.tick
pins=dict(source=fingerprint(),native=hashlib.sha256(Path(clasher_core.__file__).read_bytes()).hexdigest())
root_path=folder/f'{args.prefix}-root{b.tick}.pkl'
assert not root_path.exists()
root_path.write_bytes(cloudpickle.dumps((b,cfg,pins)))
entry=json.loads((folder/'entry.json').read_text())['sha256']
reference={n:h for n,h in entry.items() if (n.startswith('src/clasher/') and not n.startswith('src/clasher/vision/')) or n=='gamedata.json'}
root_path.with_suffix('.meta.json').write_text(json.dumps(dict(root_sha256=hashlib.sha256(root_path.read_bytes()).hexdigest(),reference=reference),indent=2)+'\n')
if row['kind']=='action':
    trace={'before':detail(b,r)}
    while action is not None and action[0]==b.tick:
        tick,seat,_,name,x,y,accepted=action
        assert b.deploy_card(seat,name,Position(x,y))==accepted
        assert r.apply_action(seat,name,x,y)==accepted
        action=next(actions,None)
    trace['after']=detail(b,r)
else:
    trace=phase_step(b,r)
(folder/f'{args.prefix}-phase{b.tick}.json').write_text(json.dumps(trace,indent=2)+'\n')
for name,state in trace.items():
    print(name,state['field_diff'][:15],flush=True)
