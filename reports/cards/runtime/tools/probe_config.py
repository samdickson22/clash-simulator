"""Probe: config(C56) vs config(C56 + pool) — are the C56 parts identical? Which pool names does config accept?"""
import json, sys, time, traceback
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from bot.players.runtime import Runtime
rt = Runtime.__new__(Runtime)
rt.root = Path('/mpac/sdicks02/repos/clasher-bot-runtime/r1'); rt.native_dir = Path('/mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1')
rt._bootstrap_paths()
sys.path.insert(0, str(REPO / 'reports/cards/tools'))
from pool import ladder_pool
import c56_controller, differential
C56 = c56_controller.CARDS
pool = [c['name'] for c in ladder_pool(rt.root / 'gamedata.json')]
print('C56', len(C56), 'pool', len(pool), 'c56-not-in-pool', sorted(set(C56) - set(pool)))
extra = sorted(set(pool) - set(C56))
print('extra', len(extra), extra)
bad = {}
for n in extra:
    try:
        differential.config((n,))
    except Exception as e:
        bad[n] = repr(e)[:200]
print('config errors', bad)
t = time.time(); a = differential.config(C56); print('c56 config s', round(time.time() - t, 1))
full = tuple(sorted(set(C56) | (set(extra) - set(bad))))
t = time.time(); b = differential.config(full); print('full config s', round(time.time() - t, 1))
for k in a:
    if k == 'cards':
        diff = [c for c in a['cards'] if json.dumps(a['cards'][c], sort_keys=True) != json.dumps(b['cards'][c], sort_keys=True)]
        print('cards c56 differing', diff)
    elif isinstance(a[k], dict):
        diff = [c for c in a[k] if json.dumps(a[k][c], sort_keys=True) != json.dumps(b[k].get(c), sort_keys=True)]
        print(k, len(a[k]), '->', len(b[k]), 'differing', diff, 'new', sorted(set(b[k]) - set(a[k]))[:40])
    else:
        print(k, 'same' if json.dumps(a[k]) == json.dumps(b[k]) else 'DIFF')
print('keys only in full', sorted(set(b) - set(a)))
json.dump(dict(extra=extra, bad=bad), open(sys.argv[1], 'w'), indent=1)
