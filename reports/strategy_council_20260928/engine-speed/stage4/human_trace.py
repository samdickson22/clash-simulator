import sys,json
from pathlib import Path
import cloudpickle
import clasher_core
from c56_gate import PLAN,play,same
from c56_controller import CARDS,resources
from differential import config,snapshot
from stage2_matches import battle
from clasher.rl.action_space import DiscreteTileActionSpace
from diagnostics import phase_step
case,tick=map(int,sys.argv[1:3]);tag=sys.argv[3]
folder=Path('reports/strategy_council_20260928/engine-speed/stage4')
ep=json.loads(PLAN.read_text())['episodes'][case]
builder,_,scripts,bots=resources();cfg=config(CARDS)
b=battle(ep,builder.loader);r=clasher_core.BattleState(snapshot(b,cfg));space=DiscreteTileActionSpace()
for t in range(tick):
 if t>=90 and t%5==0:
  packets=[builder.build_public(b,s) for s in (0,1)]
  actions=[bots[ep['styles'][s]].select_action(packets[s]) for s in (0,1)]
  for s,a in enumerate(actions):play(b,r,s,a,space)
 if t==tick-1:
  (folder/f'{tag}_before.pkl').write_bytes(cloudpickle.dumps(b))
  out=phase_step(b,r)
  (folder/f'{tag}.json').write_text(json.dumps(out,indent=2)+'\n')
  print({k:v['field_diff'] for k,v in out.items()});break
 b.step();r.step();assert same(b,r),b.tick
