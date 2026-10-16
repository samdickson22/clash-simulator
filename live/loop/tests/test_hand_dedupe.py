"""ownplay.dedupe_own_events: unit cases + the s12-m02 replay (the double-counted Musketeer at n666).
   python tests/test_hand_dedupe.py [--replay]   (--replay needs the bot runtime env, as hand_audit.py)"""
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import ownplay  # noqa: E402

checks = []


def check(name, cond):
    checks.append(bool(cond)); print(('PASS ' if cond else 'FAIL ') + name)


def sess(plays0, last_poll, started=True):
    return SimpleNamespace(started=started, last_poll=last_poll, tr=SimpleNamespace(plays=[plays0, []], stats=Counter()))


ev = lambda owner, card: dict(owner=owner, card=card, x=10.5, y=13.5, tick=0)
s = sess([(1505, 'Musketeer')], 1530)
r = dict(events=[ev(0, 'Musketeer'), ev(1, 'Musketeer'), ev(0, 'Giant')])
check('drops our duplicate of a play 25 ticks ago', ownplay.dedupe_own_events(r, s) == 1)
check('keeps the opponent event of the same card', any(e['owner'] == 1 for e in r['events']))
check('keeps our event of another card', any(e['owner'] == 0 and e['card'] == 'Giant' for e in r['events']))
check('counts own_event_dup_dropped', s.tr.stats['own_event_dup_dropped'] == 1)
s = sess([(1400, 'Musketeer')], 1530)
r = dict(events=[ev(0, 'Musketeer')])
check('keeps our event of a card played > 3 s ago (a real new play)', ownplay.dedupe_own_events(r, s) == 0 and r['events'])
s = sess([], 1530)
r = dict(events=[ev(0, 'Musketeer')])
check('keeps a perception-first own play (no recorded play yet)', ownplay.dedupe_own_events(r, s) == 0 and r['events'])
s = sess([(1505, 'Musketeer')], None, started=False)
r = dict(events=[ev(0, 'Musketeer')])
check('no-op before the session started', ownplay.dedupe_own_events(r, s) == 0)

if '--replay' in sys.argv:
    run = '/mpac/sdicks02/scratch/live-loop/runs-all/s12-m02'
    out = {}
    for fix in ('0', '1'):
        p = subprocess.run([sys.executable, '-B', str(HERE/'hand_audit.py'), run, '--json', f'/tmp/thd-{fix}.json'],
                           env=dict(os.environ, HAND_AUDIT_FIX=fix), capture_output=True, text=True, timeout=1800)
        import json
        out[fix] = json.load(open(f'/tmp/thd-{fix}.json'))[0]['stats']
    check('s12-m02 without the fix: the duplicate re-anchors the tracker (own_reanchor_play >= 1)',
          out['0'].get('own_reanchor_play', 0) >= 1)
    check('s12-m02 with the fix: no re-anchor, the duplicate is dropped',
          out['1'].get('own_reanchor_play', 0) == 0 and out['1'].get('own_event_dup_dropped', 0) >= 1)
print(f'{sum(checks)} passed, {len(checks) - sum(checks)} failed')
sys.exit(0 if all(checks) else 1)
