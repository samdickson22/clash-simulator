from differential import *
from diagnostics import detail
cards=('MightyMiner','Tornado','Knight','Zap');cfg=config(cards);b=initial(cards=cards)
b.deploy_card(0,'MightyMiner',Position(4.5,10.5))
for _ in range(20):b.step()
b.players[0].elixir=10;b.entities[7].apply_stun(3)
r=clasher_core.BattleState(snapshot(b,cfg))
assert b.activate_champion_ability(0)==r.activate_champion_ability(0)==True
for t in range(60):
 if t==5:
  assert b.deploy_card(1,'Tornado',Position(5.5,10.5))==r.apply_action(1,'Tornado',5.5,10.5)==True
 b.step();r.step()
 if battle_digest(b)!=r.digest():
  print('FAIL',b.tick,detail(b,r)['field_diff']);raise SystemExit(1)
print('PASS')
