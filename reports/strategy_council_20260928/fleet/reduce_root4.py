"""Read-only, every-tick reduction, usable with a selected frozen Mac extension."""
import argparse
import json
import os
from pathlib import Path
import sys
import hashlib

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'engine-rs'), str(ROOT/'src')]
if os.environ.get('FLEET_NATIVE_DIR'):
    sys.path.insert(0, os.environ['FLEET_NATIVE_DIR'])
import clasher_core
import cloudpickle
from c56_controller import resources, CARDS
from differential import config, battle_digest
from diagnostics import detail
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.c56_rollout_planner import C56RolloutPlanner

ap = argparse.ArgumentParser()
ap.add_argument('--root', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
args = ap.parse_args()
b, seat, search = cloudpickle.loads(args.root.read_bytes())
builder, meta, scripts, bots = resources()
cfg = config(CARDS)
p = C56RolloutPlanner(builder, bots, backend='native', seed=880004,
                      native=scripts, native_config=cfg, config=search)
chosen = p.select_action(b, seat, trace=True)
print('native', clasher_core.__file__, 'action', chosen,
      'trace', hashlib.sha256(repr(p.last).encode()).hexdigest(), flush=True)
r = p.import_root(b)
space = DiscreteTileActionSpace()
style, action = 'balanced', 109
other = int(bots[style].select_action(builder.build_public(b, 1-seat)))
assert other == scripts.select_action(r, 1-seat, style)
for actor, move in [(seat, action), (1-seat, other)]:
    space.apply_action(b, actor, move)
    scripts.apply_discrete(r, actor, move)
start = b.tick
assert battle_digest(b) == r.digest()
for elapsed in range(1, search.horizon+1):
    previous = b.clone()
    previous_r = r.snapshot()
    b.step(); r.step()
    words, index = r.rng_state()
    if battle_digest(b) != r.digest() or tuple(words)+(index,) != b.rng.getstate()[1]:
        out = dict(tick=b.tick, elapsed=elapsed, style=style, action=action,
                   native_path=clasher_core.__file__,
                   native_sha256=hashlib.sha256(Path(clasher_core.__file__).read_bytes()).hexdigest(),
                   selected_action=chosen, trace_sha256=hashlib.sha256(repr(p.last).encode()).hexdigest(),
                   decks=[x.deck for x in b.players], **detail(b, r))
        args.output.write_text(json.dumps(out, indent=2)+'\n')
        args.output.with_suffix('.pkl').write_bytes(cloudpickle.dumps((previous, previous_r, cfg)))
        print(json.dumps(dict(tick=b.tick, elapsed=elapsed, field_diff=out['field_diff'])), flush=True)
        break
    if elapsed % search.interval == 0 and elapsed < search.horizon and not b.game_over:
        for actor in (seat, 1-seat):
            move = int(bots['balanced'].select_action(builder.build_public(b, actor)))
            native_move = scripts.select_action(r, actor, 'balanced')
            assert move == native_move, (b.tick, actor, move, native_move)
            space.apply_action(b, actor, move)
            scripts.apply_discrete(r, actor, move)
else:
    args.output.write_text(json.dumps(dict(tick=b.tick, matched=True, native_path=clasher_core.__file__,
                                        trace_sha256=hashlib.sha256(repr(p.last).encode()).hexdigest()), indent=2)+'\n')
    print('paired rollout matched', flush=True)
