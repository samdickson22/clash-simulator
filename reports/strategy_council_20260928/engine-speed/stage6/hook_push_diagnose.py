"""Reduce imported knockback completion without changing the oracle."""
import hashlib
import json
from pathlib import Path

import clasher_core
import cloudpickle
from differential import battle_digest, config, snapshot
from stage2 import fingerprint

s = Path(__file__).resolve().parent
root = s / 'leap-spawn-r31-root120.pkl'
pins = json.loads(root.with_suffix('.meta.json').read_text())
assert hashlib.sha256(root.read_bytes()).hexdigest() == pins['root_sha256']
for name, expected in pins['reference'].items():
    assert hashlib.sha256((s.parents[3] / name).read_bytes()).hexdigest() == expected
b, old, _ = cloudpickle.loads(root.read_bytes())
cfg = config(tuple(old['cards']))
r = clasher_core.BattleState(snapshot(b, cfg))
fixed = r.clone()
rows = []
first_mismatch = None
for _ in range(180):
    b.step()
    r.step()
    fixed.step()
    actual = json.loads(r.snapshot())
    candidate = json.loads(fixed.snapshot())
    for e in candidate['entities']:
        if e['forced_active'] and e['push'] is None:
            p = b.entities.get(e['id'])
            if p is not None and not p.forced_movement_active:
                rows.append(dict(tick=b.tick, id=e['id'], python_forced=False,
                                 native_forced=True, native_push=e['push']))
                e['forced_active'] = False
    fixed = clasher_core.BattleState(json.dumps(candidate))
    assert battle_digest(b) == fixed.digest(), f'counterfactual failed {b.tick}'
    if first_mismatch is None and battle_digest(b) != r.digest():
        first_mismatch = b.tick
out = dict(source=fingerprint(), native=hashlib.sha256(Path(clasher_core.__file__).read_bytes()).hexdigest(),
           root_sha256=pins['root_sha256'], first_digest_mismatch=first_mismatch,
           transitions=rows, counterfactual_ticks=180, counterfactual_exact=True)
target=s/'hook-push-r37.json'
assert not target.exists()
target.write_text(json.dumps(out, indent=2)+'\n')
print(json.dumps(out), flush=True)
