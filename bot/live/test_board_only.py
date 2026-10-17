"""An opponent unit outside its full revealed set stays on the bot's board without a play or a reveal
(translate.board_only_body): one of the 8 revealed cards may be a phantom (s60-m02: Tombstone skeletons read as a
Skeletons play hid the opponent's real MiniPekka walking to our king for 12 s). Our own off-deck units stay dropped.
Full-scope runtime, in a subprocess like test_cardpool."""
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FULL_RUNTIME = os.environ.get('CLASHER_TEST_FULLPOOL_RUNTIME',
                              '/mpac/sdicks02/jobs/clasher/live-multibody-20261015/runtime-live16402b-r3')
needs_full = pytest.mark.skipif(not Path(FULL_RUNTIME).is_dir(), reason='no live16402b-r3 runtime root on this host')

CHECK = r"""
import json, os
from bot.players.runtime import Runtime
from bot.live.translate import LiveTranslator
rt = Runtime(os.environ['CLASHER_BOT_RUNTIME'])
out = {}
# board-only: 8 revealed opponent cards without MiniPekka; an enemy MiniPekka is on the board, no play, no reveal
own = ['Valkyrie', 'Archers', 'Minions', 'Cannon', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer']
tr = LiveTranslator(rt, own)
tr.plays[1] = [(10*k, c) for k, c in enumerate(['Barbarians', 'BattleRam', 'Knight', 'Musketeer', 'Tombstone',
                                                'Valkyrie', 'Wizard', 'Giant'])]
seen = []
for tick in range(300, 360, 5):
    rec = dict(tick=tick, units=[dict(cls='MiniPekka', card='MiniPekka', owner=1, x=3., y=20. - .05*(tick - 300),
                                      hp_frac=1., score=.9), dict(cls='Knight', card='Knight', owner=0, x=9., y=8.,
                                                                  hp_frac=1., score=.9)], towers=[])
    got, plays = tr.assign(rec)
    seen.append([None if g[0] is None else tr.builder.token_names[g[0][0]] for g in got])
out.update(board_only=seen[-1], board_only_plays=len(tr.tracker.played),
           board_only_stat=tr.stats['board_only:1:MiniPekka'], own_knight_dropped=tr.stats['board_dropped:0:Knight'])
print('RESULT ' + json.dumps(out))
"""


@needs_full
def test_unit_outside_a_full_revealed_set_stays_on_the_board_without_a_play(tmp_path):
    import subprocess
    import sys
    env = dict(os.environ, CLASHER_BOT_RUNTIME=FULL_RUNTIME, CLASHER_BOT_RUNTIME_PINS='live16402b-r3', PYTHONHASHSEED='0')
    for k in ('CLASHER_ROOT', 'CLASHER_EVAL_RUNTIME_ROOT', 'CLASHER_DELAY_NATIVE_DIR', 'CLASHER_LIVE_TRUE_IDS',
              'CLASHER_LIVE_OWNER_MODEL'):
        env.pop(k, None)
    r = subprocess.run([sys.executable, '-c', CHECK], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    line = next((l for l in r.stdout.splitlines() if l.startswith('RESULT ')), None)
    assert line, r.stdout[-2000:] + r.stderr[-2000:]
    out = json.loads(line[7:])
    assert out['board_only'] == ['MiniPekka', None]          # the enemy unit on the board; our off-deck Knight dropped
    assert out['board_only_plays'] == 0 and out['board_only_stat'] > 0 and out['own_knight_dropped'] > 0
