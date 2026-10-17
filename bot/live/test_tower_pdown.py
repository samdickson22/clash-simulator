"""CLASHER_LIVE_TOWER_PDOWN: births' deploy-zone test treats our princess as down when the calibrated P(fallen |
hp_read, unread) >= theta while the reader still reports it alive; unset = the reader's alive flag, as before."""
import json
from collections import Counter

from bot.live.translate import LiveTranslator, load_tower_pdown

TABLE = dict(hp_bins=[0, 50, 200, 500, 1000, 10**9], unread_bins=[1, 5, 10, 20, 30, 45, 60, 10**9],
             table={'0-50|30-45': dict(p_down=.97), '200-500|30-45': dict(p_down=.984),
                    '200-500|1-5': dict(p_down=.507), '1000-1000000000|10-20': dict(p_down=.03)})


class Stub:
    stats = None
    towers = staticmethod(LiveTranslator.towers)

    def __init__(self, pdown):
        self._pdown, self.stats = pdown, Counter()


def rec(left, right=None):
    t = [dict(owner=0, kind='princess', side='left', **left)]
    if right:
        t.append(dict(owner=0, kind='princess', side='right', **right))
    return dict(tick=3260, towers=t)


def test_off_keeps_the_reader_flag_and_on_uses_the_calibration(tmp_path):
    (tmp_path / 't.json').write_text(json.dumps(TABLE))
    on = Stub(load_tower_pdown(f"{tmp_path / 't.json'}:0.9"))
    off = Stub(None)
    falling = rec(dict(alive=True, hp_frac=.19, hp_read=415, unread=42))            # s69-m04, 1.8 s before the death
    assert LiveTranslator._births_towers(off, falling) == {'left': True, 'right': True}
    assert LiveTranslator._births_towers(on, falling)['left'] is False and on.stats['tower_pdown_pocket'] == 1
    # freshly read / long unread at high HP / just started being unread: stays alive
    for t in (dict(alive=True, hp_frac=.19, hp_read=415, unread=0), dict(alive=True, hp_frac=1., hp_read=2184, unread=12),
              dict(alive=True, hp_frac=.19, hp_read=415, unread=2)):
        assert LiveTranslator._births_towers(on, rec(t))['left'] is True
    # an already-dead tower stays dead; the other side is untouched
    dead = dict(alive=False, hp_frac=0., hp_read=0, unread=80)
    got = LiveTranslator._births_towers(on, rec(dead, dict(alive=True, hp_frac=.01, hp_read=22, unread=31)))
    assert got == {'left': False, 'right': False}
    assert load_tower_pdown(None) is None and load_tower_pdown(f"{tmp_path / 't.json'}")[1] == .9
