from differential import *
from diagnostics import detail
cards=('FireSpirits','GoblinHut','Knight','Zap')
cfg=config(cards);b=initial(cards=cards)
for card,seat,y in [('FireSpirits',0,12.5),('Knight',1,14),('GoblinHut',1,15)]:
 b._spawn_unit_at_position(Position(4.5,y),seat,b.card_loader.get_card(card),deploy_delay_override=0,snap_to_valid=False)
spirit,knight,hut=b.entities[7],b.entities[8],b.entities[9]
knight.apply_stun(10)
for _ in range(10):
 b.step()
 if getattr(spirit,'_self_projectile_launched',False):break
assert getattr(spirit,'_self_projectile_launched',False)
hut.take_damage(hut.hitpoints)
children=[e for e in b.entities.values() if e.id>=10 and e.entity_kind==0]
assert children
r=clasher_core.BattleState(snapshot(b,cfg))
print('root',b.tick,'sourcekind',spirit.entity_kind,'children',[(e.id,e.position.x,e.position.y,e._death_spawn_target_immunity_elapsed_ms) for e in children],flush=True)
for _ in range(20):
 b.step();r.step()
 if battle_digest(b)!=r.digest():
  print('FAIL',b.tick,detail(b,r)['field_diff']);raise SystemExit(1)
print('PASS',all(not e.is_alive for e in children))
