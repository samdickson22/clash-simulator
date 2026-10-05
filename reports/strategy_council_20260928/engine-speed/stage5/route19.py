import json
from pathlib import Path
import cloudpickle
from c56_controller import CARDS,resources
from differential import config,battle_digest
from diagnostics import detail,phase_step
from clasher.rl.c56_rollout_planner import C56RolloutPlanner
from qualify import write

here=Path(__file__).resolve().parent
b,seat=cloudpickle.loads((here/'failure19.pkl').read_bytes())
builder,_,scripts,bots=resources();cfg=config(CARDS)
p=C56RolloutPlanner(builder,bots,backend='native',native=scripts,native_config=cfg)
r=p.import_root(b)
other=scripts.select_action(r,1-seat,'balanced')
for s,a in ((seat,714),(1-seat,other)):
    if a!=2304: assert p.space.apply_action(b,s,a)==scripts.apply_discrete(r,s,a)
for tick in range(160):
    before=b.clone();nr=r.clone()
    b.step();r.step()
    rstate=json.loads(r.snapshot())
    for e in rstate['entities']:
        pe=b.entities.get(e['id'])
        if pe is not None and e['id']==31:
            route=[list(v) for v in (getattr(pe,'_native_ground_route_cells',None) or [])]
            if route!=e['route']:
                print('first route difference',b.tick,route,e['route'],pe._knockback_target,e['push'],pe._native_natural_movement_active,e['moving'],flush=True)
                write(here/'routephase19.json',phase_step(before,nr))
                raise SystemExit()
    if battle_digest(b)!=r.digest():
        out=detail(b,r);write(here/'difference19.json',out)
        write(here/'phase19.json',phase_step(before,nr))
        print(b.tick,json.dumps(out['field_diff']),flush=True)
        break
    if (tick+1)%10==0 and tick+1<160:
        for actor in (seat,1-seat):
            pa=bots['balanced'].select_action(builder.build_public(b,actor));ra=scripts.select_action(r,actor,'balanced')
            assert pa==ra,(b.tick,actor,pa,ra)
            if pa!=2304: assert p.space.apply_action(b,actor,pa)==scripts.apply_discrete(r,actor,ra)
else:print('no state mismatch')
