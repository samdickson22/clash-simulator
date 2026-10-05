"""Retain the first mixed ranged failure and its actual phase transitions."""
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
row=json.loads((folder/'requested-r11b-interactions.json').read_text())['results']['1']
cfg=config(('Hunter','ElectroWizard','IceWizard','AxeMan','Knight','Musketeer','Zap','Cannon','Archers','Giant','Fireball'))
b=battle(row['episode'],ContractV5ObservationBuilder().loader)
r=clasher_core.BattleState(snapshot(b,cfg));actions=iter(row['actions']);action=next(actions,None)
while b.tick<row['python']['tick']-1:
    while action is not None and action[0]==b.tick:
        tick,seat,_,name,x,y,accepted=action
        assert b.deploy_card(seat,name,Position(x,y))==accepted
        assert r.apply_action(seat,name,x,y)==accepted
        action=next(actions,None)
    b.step();r.step();assert battle_digest(b)==r.digest(),b.tick
pins=dict(source=fingerprint(),native=hashlib.sha256(Path(clasher_core.__file__).read_bytes()).hexdigest())
(folder/'ranged-root4862-r11b.pkl').write_bytes(cloudpickle.dumps((b,cfg,pins)))
trace=phase_step(b,r)
(folder/'ranged-phase4863-r11b.json').write_text(json.dumps(trace,indent=2)+'\n')
for name,state in trace.items():
    print(name,state['field_diff'][:15],flush=True)
