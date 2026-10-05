import json
from pathlib import Path
from differential import *
from diagnostics import phase_step, detail
cards=('Golem','Zap','Knight','Musketeer');cfg=config(cards)
b=initial(560418,cards=cards);b.players[0].elixir=10
b.deploy_card(0,'Golem',Position(4.5,13.5));b.deploy_card(1,'Knight',Position(4.5,18.5))
for _ in range(60): b.step()
g=b.entities[7];g.hitpoints=1;b.players[1].elixir=10
b.deploy_card(1,'Zap',Position(g.position.x,g.position.y));b.step()
r=clasher_core.BattleState(snapshot(b,cfg))
v=phase_step(b,r)
Path('reports/strategy_council_20260928/engine-speed/stage4/golem_import62.json').write_text(json.dumps(v,indent=2))
print(detail(b,r)['field_diff'])
