"""Diagnostic only: prove the stagger filter causes root 4's first divergence.

Never used for acceptance; no source or fixture is modified on disk.
"""
import cloudpickle
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'engine-rs'), str(ROOT/'src')]
import clasher_core
from clasher.entities import ChainLightning
from differential import battle_digest

OUT = Path('/mpac/sdicks02/jobs/clasher')
before, native_json, cfg = cloudpickle.loads((OUT/'root4-linux-action109.pkl').read_bytes())
assert before.tick == 1006
original = ChainLightning._can_chain_to
rows = []
for filtered in (False, True):
    b = before.clone()
    native = clasher_core.BattleState(native_json)
    if filtered:
        ChainLightning._can_chain_to = lambda self, entity: original(self, entity) and entity.spawn_stagger_remaining <= 1e-9
    try:
        b.step(); native.step()
        chain = b.entities[128]
        raw = next(e for e in json.loads(native.snapshot())['entities'] if e['id']==128)
        rows.append(dict(diagnostic_stagger_filter=filtered, tick=b.tick,
                         python_target=chain.current_target_id, native_target=raw['shot_target'],
                         python_position=[chain.position.x,chain.position.y],
                         native_position=[raw['x'],raw['y']],
                         digest_equal=battle_digest(b)==native.digest(),
                         target127_stagger=b.entities[127].spawn_stagger_remaining))
    finally:
        ChainLightning._can_chain_to = original
assert rows[0]['python_target']==127 and rows[0]['native_target']==124 and not rows[0]['digest_equal']
assert rows[1]['python_target']==124 and rows[1]['digest_equal']
out=dict(diagnostic_only=True, accepted=False, result=rows,
         explanation='Adding the native stagger exclusion to the Python target chooser alone reproduces the native first-tick digest. The oracle remains unchanged.')
(OUT/'chain-stagger-counterfactual.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
