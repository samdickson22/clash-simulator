"""Replay every recorded Python candidate/score/trace hash on final pinned native code."""
import hashlib
import json
from pathlib import Path
import sys
import time
import qualify
from scope_pins import fingerprint,pins
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.c56_rollout_planner import C56RolloutPlanner

here=Path(__file__).resolve().parent
reference_path=here/'parity-r3.json'
reference=json.loads(reference_path.read_text())
assert reference['complete'] and len(reference['results'])>=200
before=pins()

def check(b,seat,builder,bots,scripts,cfg,index,search_cfg):
    n=C56RolloutPlanner(builder,bots,backend='native',seed=880000+index,native=scripts,native_config=cfg,config=search_cfg)
    start=time.perf_counter();action=n.select_action(b,seat,trace=True)
    got=hashlib.sha256(repr(n.last).encode()).hexdigest();want=reference['results'][index]
    assert got==want['trace_sha256'] and action==want['action'],('recorded Python trace',index,got,want)
    return dict(index=index,tick=b.tick,seat=seat,action=action,trace_sha256=got,candidates=len(n.last['candidates']),wall=time.perf_counter()-start)

qualify.check=check;qualify.fingerprint=fingerprint;qualify.plannerspace=DiscreteTileActionSpace()
sys.argv=[__file__,'--roots','200','--output',str(here/'parity-scoped.json')]
qualify.main()
assert pins()==before,'runtime changed during replay'
qualify.write(here/'scoped-sources.json',dict(fingerprint=fingerprint(),files=before,reference_sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),reason='Unrelated vision/l1_training.py changed during original tests. This replay binds all200 exact recorded Python traces to the final scoped native runtime; Python engine sources outside vision remain entry-identical.'))
