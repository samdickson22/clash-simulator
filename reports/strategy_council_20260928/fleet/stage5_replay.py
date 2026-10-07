"""Original Stage 5 replay_qualified.py gate with fleet-owned output paths."""
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / 'reports/strategy_council_20260928/engine-speed/stage5'
OUT = Path('/mpac/sdicks02/jobs/clasher')
sys.path.insert(0, str(STAGE))
import qualify
from scope_pins import fingerprint, pins
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.c56_rollout_planner import C56RolloutPlanner

reference_path = STAGE / 'parity-r3.json'
reference = json.loads(reference_path.read_text())
assert reference['complete'] and len(reference['results']) >= 200
before = pins()


def check(b, seat, builder, bots, scripts, cfg, index, search_cfg):
    native = C56RolloutPlanner(builder, bots, backend='native', seed=880000+index,
                              native=scripts, native_config=cfg, config=search_cfg)
    start = time.perf_counter()
    action = native.select_action(b, seat, trace=True)
    got = hashlib.sha256(repr(native.last).encode()).hexdigest()
    want = reference['results'][index]
    if got != want['trace_sha256'] or action != want['action']:
        qualify.write(OUT / 'stage5-first-difference.json',
                      dict(index=index, tick=b.tick, got=got, expected=want, trace=native.last))
        raise AssertionError(('recorded Python trace', index, got, want))
    return dict(index=index, tick=b.tick, seat=seat, action=action,
                trace_sha256=got, candidates=len(native.last['candidates']),
                wall=time.perf_counter()-start)


qualify.check = check
qualify.fingerprint = fingerprint
qualify.plannerspace = DiscreteTileActionSpace()
sys.argv = [__file__, '--roots', '200', '--output', str(OUT / 'stage5-replay-linux.json')]
qualify.main()
assert pins() == before, 'runtime changed during replay'
qualify.write(OUT / 'stage5-replay-pins.json', dict(
    fingerprint=fingerprint(), files=before,
    reference_sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),
    driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
print('PASS: all 200 recorded Mac Python action/score/trace hashes reproduced by Linux native engine')
