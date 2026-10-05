import json
from pathlib import Path
from differential import *
from diagnostics import phase_step
from clasher.entities import TimedExplosive
cards=('MightyMiner','Knight','Archers','Zap')
cfg=config(cards);b=initial(cards=cards)
b.deploy_card(0,'MightyMiner',Position(4.5,10.5));b.deploy_card(1,'Knight',Position(4.5,21.5))
for _ in range(20): b.step()
miner,knight=b.entities[7],b.entities[8]
knight.position=Position(miner.position.x+1,miner.position.y);knight.hitpoints=100000
container=TimedExplosive(id=b.next_entity_id,position=Position(miner.position.x,miner.position.y),player_id=1,card_stats=knight.card_stats,hitpoints=1,max_hitpoints=1,damage=0,range=0,sight_range=0,explosion_timer=999)
b.entities[container.id]=container;b.next_entity_id+=1;b.players[0].elixir=10
r=clasher_core.BattleState(snapshot(b,cfg));b.activate_champion_ability(0);r.activate_champion_ability(0)
for _ in range(22):
 b.step();r.step()
 assert battle_digest(b)==r.digest(),b.tick
out=phase_step(b,r)
Path('reports/strategy_council_20260928/engine-speed/stage4/mighty_container43.json').write_text(json.dumps(out,indent=2))
print({k:v['field_diff'] for k,v in out.items()})
