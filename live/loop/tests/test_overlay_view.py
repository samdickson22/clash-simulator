"""Overlay view toggles: by default the page draws only what the bot uses (rec units), not sub-threshold candidates,
the heatmap or the old model's units; /view/<key> toggles them; candidates < .3 are drawn faint.
   python tests/test_overlay_view.py"""
import json
import socket
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overlay import Overlay  # noqa: E402

checks = []


def check(name, cond):
    checks.append(bool(cond)); print(('PASS ' if cond else 'FAIL ') + name)


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


port = free_port()
ov = Overlay(port, host='127.0.0.1', every=1)
frame = np.full((1280, 720, 3), 90, np.uint8)
rec = dict(units=[dict(owner=1, cls='Giant', x=9.0, y=20.0, score=.8)], towers=[], hand={},
           units_model=[dict(owner=0, cls='Knight', x=4.0, y=8.0, score=.7)])
cand = [dict(owner=1, cls='SkeletonArmy', x=14.0, y=12.0, score=.09), dict(owner=0, cls='Archers', x=5.0, y=14.0, score=.35)]
heat = np.zeros((2, 64, 36), np.float32); heat[1, 30:34, 10:14] = .9


def render(**kw):
    ov.update(frame, rec, 'battle', 100, 5.0, None, **kw)
    return cv2.imdecode(np.frombuffer(ov.jpg, np.uint8), cv2.IMREAD_COLOR).astype(int)


base = render(heat=None, units_lo=())
default = render(heat=heat, units_lo=cand)
check('default view ignores candidates + heatmap (same as a render without them)', np.abs(default - base).mean() < .5)


def post(path):
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=b'', method='POST')
    with urllib.request.urlopen(req, timeout=3) as r:
        return r.read().decode()


check('/view/candidates toggles on', 'shown' in post('/view/candidates'))
on = render(heat=heat, units_lo=cand)
check('candidates + heatmap drawn when toggled on', np.abs(on - base).sum() > 5000)
st = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{port}/state', timeout=3).read())
check('/state reports the view', st['view'] == dict(candidates=True, model_units=False))
# faint < .3: the SkeletonArmy candidate (.09) is drawn darker than the Archers one (.35)
only_low = render(heat=None, units_lo=cand[:1]); only_hi = render(heat=None, units_lo=cand[1:])
check('a candidate under .3 is drawn faint (dimmer than one above .3)',
      np.abs(only_low - base).sum() < np.abs(only_hi - base).sum())
post('/view/candidates')
check('old model units hidden by default', np.abs(render(heat=None, units_lo=()) - base).mean() < .5)
post('/view/model_units')
check('old model units drawn when toggled on', np.abs(render(heat=None, units_lo=()) - base).sum() > 5000)
post('/view/model_units')
# LL_UNITS_BOT: the label is the card the bot got ("raw->card" where the detector class differs), the colour its owner
import overlay as OV  # noqa: E402
check('_norm: archer == Archers, barbarian != Knight', OV._norm('archer') == OV._norm('Archers') and OV._norm('barbarian') != OV._norm('Knight'))
rec['units'] = [dict(owner=1, cls='Knight', card='Knight', x=9.0, y=20.0, score=.8)]
proxy = render(heat=None, units_lo=())
rec['units_bot'] = [dict(card='Knight', owner=1, raw='knight')]
check('units_bot with the same card + owner draws the same as without', np.abs(render(heat=None, units_lo=()) - proxy).mean() < .5)
rec['units_bot'] = [dict(card='Barbarians', owner=1, raw='barbarian', alias='Knight')]
true = render(heat=None, units_lo=())
check('units_bot card replaces the proxy label', np.abs(true - proxy).sum() > 2000)
rec['units_bot'] = [dict(card='Barbarians', owner=0, raw='barbarian', alias='Knight')]
check('units_bot owner sets the colour (ours = blue)', np.abs(render(heat=None, units_lo=()) - true).sum() > 2000)
rec['units_bot'] = [dict(card='Barbarians', owner=1, raw='barbarian'), dict(card='X', owner=1, raw='x')]
check('units_bot of another length is ignored (proxy drawing)', np.abs(render(heat=None, units_lo=()) - proxy).mean() < .5)
del rec['units_bot']
ov.close()
print(f'{sum(checks)} passed, {len(checks) - sum(checks)} failed')
sys.exit(0 if all(checks) else 1)
