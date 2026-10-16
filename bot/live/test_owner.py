"""The learned temporal owner switch (CLASHER_LIVE_OWNER_MODEL): owner tracks, fail-closed loading, the translator hook
and its catch-up behaviour. The model here is a tiny stand-in that votes with the track's opponent fraction."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from bot.live.owner_track import NAMES, OwnerTracks
from bot.live.playdet.trees import FORMAT, Trees

ROOT = Path(__file__).resolve().parents[2]
CLASSES = ROOT / 'live/yolo_synth/classes.json'
OWN = ['Valkyrie', 'Archers', 'Minions', 'Cannon', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer']


def frac_model():
    """One tree: frac_opp <= .5 -> raw -4 (ours), else +4 (opponent)."""
    j = NAMES.index('frac_opp')
    m = dict(format=FORMAT, names=list(NAMES), feature=[[j]], threshold=[[.5]], left=[[~0]], right=[[~1]],
             value=[[-4., 4.]], depth=1, base=0., theta=.5)
    m['sha'] = hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()
    return m


def spec(tmp_path, bad=False):
    (tmp_path / 'm.json').write_text(json.dumps(frac_model()))
    s = dict(model='m.json', sha256='0'*64 if bad else hashlib.sha256((tmp_path / 'm.json').read_bytes()).hexdigest(),
             classes=str(CLASSES), classes_sha256=hashlib.sha256(CLASSES.read_bytes()).hexdigest(), theta=.5)
    p = tmp_path / 'owner.json'
    p.write_text(json.dumps(s))
    return p


def unit(owner, x, y, card='Knight'):
    return dict(cls=card, card=card, owner=owner, x=x, y=y, hp_frac=None, score=.8)


def test_tracks_follow_bodies_whatever_the_detector_team():
    tr = OwnerTracks()
    ids = []
    for k, o in enumerate([1, 1, 0, 1, 1]):                 # one enemy knight, read as ours once
        rows, i = tr.update(100 + 5*k, [unit(o, 9., 25. - .2*k)], ['knight'])
        ids += i
        assert len(rows[0]) == len(NAMES)
    assert len(set(ids)) == 1
    assert rows[0][NAMES.index('frac_opp')] == pytest.approx(.8)


def test_a_lost_and_found_body_carries_its_previous_track():
    tr = OwnerTracks()
    for k in range(4):
        tr.update(100 + 5*k, [unit(1, 9., 25.)], ['knight'])
    rows, _ = tr.update(160, [unit(0, 9.3, 24.8)], ['knight'])  # gap > max_gap: a new track, next to the old one
    r = rows[0]
    assert r[NAMES.index('n_obs')] == 1 and r[NAMES.index('prev_frac_opp')] == 1. and r[NAMES.index('prev_dist')] < 1.


def test_loading_fails_closed(tmp_path):
    from bot.live.translate import load_owner_model
    trees, theta, classes = load_owner_model(spec(tmp_path))
    assert isinstance(trees, Trees) and theta == .5 and 'knight' in classes
    with pytest.raises(ValueError, match='sha256'):
        load_owner_model(spec(tmp_path, bad=True))


class Stub:
    """What learned_owners() reads."""
    def __init__(self, tmp_path):
        from collections import Counter
        from bot.live.translate import load_owner_model
        self.owner_model = load_owner_model(spec(tmp_path))
        self.owner_tracks = OwnerTracks(self.owner_model[2], OWN)
        self._owner_last, self.public_events, self.stats = None, [], Counter()


def test_learned_owner_fixes_a_transient_flip_and_keeps_the_detector_team(tmp_path):
    from bot.live.translate import LiveTranslator
    st = Stub(tmp_path)
    got = []
    for k, o in enumerate([1, 1, 1, 0, 1]):
        rec = dict(tick=100 + 5*k, timestamp_ms=1000*k, units=[unit(o, 9., 25. - .2*k)], units_yolo=['knight'])
        got.append(LiveTranslator.learned_owners(st, rec)[0])
    assert [u['owner'] for u in got] == [1, 1, 1, 1, 1]
    assert got[3]['owner_det'] == 0 and 'owner_det' not in got[2]
    assert st.stats['owner_learned:0->1'] == 1


def test_a_repeated_frame_reuses_the_owners_without_advancing(tmp_path):
    from bot.live.translate import LiveTranslator
    st = Stub(tmp_path)
    rec = dict(tick=100, timestamp_ms=5, units=[unit(1, 9., 25.)], units_yolo=['knight'])
    LiveTranslator.learned_owners(st, rec)
    n = len(st.owner_tracks.tracks[0]['owners'])
    again = LiveTranslator.learned_owners(st, dict(rec, _synthetic=True))
    assert again[0]['owner'] == 1 and len(st.owner_tracks.tracks[0]['owners']) == n


def test_unset_switch_leaves_units_untouched():
    import os
    from bot.live import translate
    assert 'CLASHER_LIVE_OWNER_MODEL' not in os.environ or pytest.skip('switch set in this environment')
    src = Path(translate.__file__).read_text()
    assert "self.owner_model = load_owner_model(spec) if spec else None" in src
