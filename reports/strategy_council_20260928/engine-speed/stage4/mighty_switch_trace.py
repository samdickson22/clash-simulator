import json
from pathlib import Path
from differential import *
from diagnostics import phase_step
cards=('MightyMiner','Knight','Archers','Zap')
cfg=config(cards)
b=initial(cards=cards)
b.deploy_card(0,'MightyMiner',Position(4.5,13.5))
b.deploy_card(1,'Knight',Position(4.5,18.5))
b.entities[7].hitpoints=b.entities[8].hitpoints=100000
for _ in range(100): b.step()
b.entities[7].apply_stun(1.2)
b.players[0].elixir=10
r=clasher_core.BattleState(snapshot(b,cfg))
b.activate_champion_ability(0);r.activate_champion_ability(0)
for _ in range(44):
 b.step();r.step()
 assert battle_digest(b)==r.digest(),b.tick
out=phase_step(b,r)
Path('reports/strategy_council_20260928/engine-speed/stage4/mighty_switch145.json').write_text(json.dumps(out,indent=2))
print({k:v['field_diff'] for k,v in out.items()})
print('python', entity(b.entities[7]))
print('native', next(e for e in json.loads(r.snapshot())['entities'] if e['id']==7))
