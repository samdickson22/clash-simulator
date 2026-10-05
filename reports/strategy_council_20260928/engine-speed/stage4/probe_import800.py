import json
import cloudpickle
import stage4_matches as m
from differential import *
from diagnostics import phase_step
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
cfg=config(tuple(dict.fromkeys((*m.PILOT,*m.BUNDLES['B1'],*m.BUNDLES['B2']))))
original=m.snapshot
roots=[]
def capture(b,cfg):
 if b.tick==800:roots.append(b.clone())
 return original(b,cfg)
m.snapshot=capture
m.match('B2',2,cfg,ContractV5ObservationBuilder(),ticks=800)
b=roots[0]
(ES/'stage4/b2_case2_root800.pkl').write_bytes(cloudpickle.dumps((b,cfg)))
r=clasher_core.BattleState(snapshot(b,cfg))
for _ in range(25):
 bp,rp=b.clone(),r.clone();b.step();r.step()
 pe=b.entities.get(52);re=next((e for e in json.loads(r.snapshot())['entities'] if e['id']==52),None)
 if pe and re:print(b.tick,'python',pe.attack_cooldown,pe.target_id,pe._attack_windup_active,pe._has_attacked_once,'rust',re['cooldown'],re['target'],re['windup'],re['started'],flush=True)
 if battle_digest(b)!=r.digest():
  out=phase_step(bp,rp);(ES/'stage4/import819_trace.json').write_text(json.dumps(out,indent=2));break
