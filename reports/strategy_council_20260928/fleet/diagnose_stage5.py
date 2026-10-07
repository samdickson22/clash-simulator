"""Preserve root 4 and compare current Python/native traces to the Mac receipt."""
import cloudpickle
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / 'reports/strategy_council_20260928/engine-speed/stage5'
OUT = Path('/mpac/sdicks02/jobs/clasher')
sys.path.insert(0, str(STAGE))
import qualify
from scope_pins import fingerprint
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.c56_rollout_planner import C56RolloutPlanner


def differences(a, b, path='root'):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in a:
            yield from differences(a[key], b[key], f'{path}.{key}')
    elif isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
        if len(a) != len(b):
            yield dict(path=path+'.length', python=len(a), native=len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            yield from differences(x, y, f'{path}[{i}]')
    elif a != b:
        yield dict(path=path, python=a, native=b,
                   python_hex=a.hex() if isinstance(a, float) else None,
                   native_hex=b.hex() if isinstance(b, float) else None)


def check(b, seat, builder, bots, scripts, cfg, index, search_cfg):
    if index != 4:
        return dict(index=index, diagnostic_skipped=True)
    (OUT/'stage5-root4.pkl').write_bytes(cloudpickle.dumps((b, seat, search_cfg)))
    ref = json.loads((STAGE/'parity-r3.json').read_text())['results'][index]
    traces = []
    for backend in ('python', 'native'):
        planner = C56RolloutPlanner(builder, bots, backend=backend, seed=880000+index,
                                   native=scripts, native_config=cfg, config=search_cfg)
        action = planner.select_action(b, seat, trace=True)
        traces.append(planner.last)
        qualify.write(OUT/f'stage5-root4-{backend}.json', dict(action=action, trace=planner.last))
        print(backend, action, hashlib.sha256(repr(planner.last).encode()).hexdigest(), flush=True)
    diff = list(differences(*traces))
    out = dict(index=index, tick=b.tick, seat=seat, expected=ref, differences=diff,
               python_matches_mac=hashlib.sha256(repr(traces[0]).encode()).hexdigest()==ref['trace_sha256'])
    qualify.write(OUT/'stage5-root4-diagnosis.json', out)
    print(json.dumps(dict(count=len(diff), first=diff[:8], python_matches_mac=out['python_matches_mac'])), flush=True)
    return dict(index=index, diagnostic=True)


qualify.check = check
qualify.fingerprint = fingerprint
qualify.plannerspace = DiscreteTileActionSpace()
sys.argv = [__file__, '--roots', '5', '--output', str(OUT/'stage5-diagnostic-progress.json')]
qualify.main()
