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


def test_v1_rows_are_the_v2_rows_without_the_pteam_columns():
    from bot.live.owner_track import NAMES_V2, PTEAM
    a, b = OwnerTracks(), OwnerTracks(names=NAMES_V2)
    for k, o in enumerate([1, 0, 1, 1]):
        us = [unit(o, 9., 25. - .2*k), unit(0, 4., 6.)]
        info = [dict(p_team=.9 - .3*(o == 0)), dict(p_team=.05)]
        r1, _ = a.update(100 + 5*k, us, ['knight', 'archer'], (), info)
        r2, _ = b.update(100 + 5*k, us, ['knight', 'archer'], (), info)
        assert [len(r) for r in r1] == [len(NAMES)]*2 and [r[:len(NAMES)] for r in r2] == r1
        assert all(len(r) == len(NAMES) + len(PTEAM) for r in r2)


def test_pteam_history_and_unknown_values():
    from bot.live.owner_track import NAMES_V2
    tr = OwnerTracks(names=NAMES_V2)
    col = {n: i for i, n in enumerate(NAMES_V2)}
    rows, _ = tr.update(100, [unit(1, 9., 25.)], ['knight'])          # no units_yolo_info (older runs)
    assert rows[0][col['pteam_known']] == 0. and rows[0][col['cur_pteam']] == -1. and rows[0][col['mean_pteam']] == -1.
    for k, p in enumerate([.9, .3, .8]):
        rows, _ = tr.update(105 + 5*k, [unit(1, 9., 25.)], ['knight'], (), [dict(p_team=p)])
    r = rows[0]
    assert r[col['pteam_known']] == 1. and r[col['cur_pteam']] == pytest.approx(.8)
    assert r[col['mean_pteam']] == pytest.approx(2./3) and r[col['min_pteam']] == pytest.approx(.3)
    assert r[col['birth_pteam']] == -1.                               # born before p_team was known
    rows, _ = tr.update(125, [unit(1, 9., 25.)], ['knight'], (), [dict(p_team=.7), dict(p_team=.1)])  # unaligned
    assert rows[0][col['pteam_known']] == 0. and rows[0][col['mean_pteam']] == pytest.approx(2./3)


def test_a_v2_model_loads_and_the_translator_passes_pteam(tmp_path):
    from bot.live.owner_track import NAMES_V2
    from bot.live.translate import LiveTranslator, load_owner_model
    j = NAMES_V2.index('cur_pteam')                                   # one tree: P(opp) follows this frame's p_team
    m = dict(format=FORMAT, names=list(NAMES_V2), feature=[[j]], threshold=[[.5]], left=[[~0]], right=[[~1]],
             value=[[-4., 4.]], depth=1, base=0., theta=.5)
    st = Stub(tmp_path)                                               # (writes the v1 stand-in first)
    s = json.loads((tmp_path / 'owner.json').read_text())
    (tmp_path / 'm.json').write_text(json.dumps(m))
    s['sha256'] = hashlib.sha256((tmp_path / 'm.json').read_bytes()).hexdigest()
    (tmp_path / 'owner.json').write_text(json.dumps(s))
    st.owner_model = load_owner_model(tmp_path / 'owner.json')
    st.owner_tracks = OwnerTracks(st.owner_model[2], OWN, tuple(st.owner_model[0].names))
    rec = dict(tick=100, timestamp_ms=5, units=[unit(0, 9., 25.)], units_yolo=['knight'],
               units_yolo_info=[dict(p_team=.9, score=.8)])
    assert LiveTranslator.learned_owners(st, rec)[0]['owner'] == 1
    with pytest.raises(ValueError, match='features'):
        bad = dict(m, names=list(NAMES_V2[:-1]) + ['nope'])
        (tmp_path / 'm.json').write_text(json.dumps(bad))
        s['sha256'] = hashlib.sha256((tmp_path / 'm.json').read_bytes()).hexdigest()
        (tmp_path / 'owner.json').write_text(json.dumps(s))
        load_owner_model(tmp_path / 'owner.json')


def _classes():
    return {e['name']: e for e in json.loads(CLASSES.read_text())['names']}


def test_v1_rows_unchanged_by_the_swarm_columns():
    from bot.live.owner_track import NAMES_V4, SWARM
    a, b = OwnerTracks(_classes()), OwnerTracks(_classes(), names=NAMES_V4)
    for k in range(4):
        us = [unit(0, 9. + .1*j, 20. + .3*k, 'Bats') for j in range(3)] + [unit(1, 4., 25.)]
        raw = ['bat', 'bat', 'bat-evolution', 'knight']
        r1, _ = a.update(100 + 5*k, us, raw)
        r2, _ = b.update(100 + 5*k, us, raw)
        assert [r[:len(NAMES)] for r in r2] == r1 and all(len(r) == len(NAMES) + len(SWARM) for r in r2)


def test_swarm_context_for_a_body_of_our_swarm_read_as_the_opponent():
    """Our 4 Bats fly up the lane; in the 4th frame one of them (an evolved-Bat raw class) is read as the opponent's
    and is too far from its track to continue it. Its swarm columns: 3 of ours within 2.5 tiles now (raw classes of
    one card count together), 3 of ours near this spot in the previous frame, no other opponent Bats, and a mostly-ours
    Bats track that went unmatched in this frame next to it. A lone opponent Knight has no swarm."""
    from bot.live.owner_track import NAMES_V4, SWARM
    tr = OwnerTracks(_classes(), names=NAMES_V4)
    col = {n: len(NAMES) + k for k, n in enumerate(SWARM)}
    for k in range(3):
        us = [unit(0, 9. + .5*j, 14. + 1.*k, 'Bats') for j in range(4)] + [unit(1, 3., 27., 'Knight'),
                                                                           unit(1, 13., 18., 'Bats')]
        tr.update(100 + 5*k, us, ['bat', 'bat', 'bat', 'bat-evolution', 'knight', 'bat'])
    # frame 4: the opponent's Bat jumps out of reach of its own track too: a new body whose only unmatched Bats track
    # nearby is the opponent's, which is not ours to lose
    us = [unit(0, 9. + .5*j, 17., 'Bats') for j in range(3)] + [unit(1, 11.3, 17.4, 'Bats'), unit(1, 3., 27., 'Knight'),
                                                                unit(1, 15.2, 19.5, 'Bats')]
    rows, _ = tr.update(115, us, ['bat', 'bat', 'bat', 'bat-evolution', 'knight', 'bat'])
    flip, knight, theirs = rows[3], rows[4], rows[5]
    assert theirs[col['sw_lost_ours_d']] == 99. and theirs[col['sw_ours_n']] == 0
    assert flip[col['sw_ours_n']] == 3 and flip[col['sw_ours_d']] < 1.5 and flip[col['sw_opp_n']] == 0
    assert flip[col['sw_ours_recent']] == 3          # the previous frame: 3 of the 4 within 2.5 tiles of this spot
    assert 1.5 < flip[col['sw_lost_ours_d']] < 2. and flip[col['sw_lost_ours_gap']] == 5    # beyond the track radius
    assert knight[col['sw_ours_n']] == 0 and knight[col['sw_ours_recent']] == 0 and knight[col['sw_lost_ours_d']] == 99.


def test_a_v4_model_loads(tmp_path):
    from bot.live.owner_track import NAMES_V4
    from bot.live.translate import load_owner_model
    m = frac_model()
    m['names'] = list(NAMES_V4); m.pop('sha')
    (tmp_path / 'm.json').write_text(json.dumps(m))
    s = dict(model='m.json', sha256=hashlib.sha256((tmp_path / 'm.json').read_bytes()).hexdigest(),
             classes=str(CLASSES), classes_sha256=hashlib.sha256(CLASSES.read_bytes()).hexdigest(), theta=.5)
    (tmp_path / 'owner.json').write_text(json.dumps(s))
    trees, theta, classes = load_owner_model(tmp_path / 'owner.json')
    assert trees.names == list(NAMES_V4) and 'bat-evolution' in classes


@pytest.mark.parametrize('names,expect', [('v1', [(80, 'Knight', 9., 25.)]),
                                          ('v4', [(80, 'Knight', 9., 25.), (90, 'Bats', 9., 12.)])])
def test_own_plays_fed_to_the_owner_tracks(tmp_path, names, expect):
    """A v1.1 model sees our accepted own plays, exactly as deployed; a v1.3 (swarm) model sees every own deploy
    before the cycle guard, as owner_dataset.capture builds its datasets."""
    from bot.live.owner_track import NAMES_V4
    from bot.live.translate import LiveTranslator, load_owner_model
    st = Stub(tmp_path)
    if names == 'v4':
        m = frac_model(); m['names'] = list(NAMES_V4); m.pop('sha')
        (tmp_path / 'm.json').write_text(json.dumps(m))
        s = json.loads((tmp_path / 'owner.json').read_text())
        s['sha256'] = hashlib.sha256((tmp_path / 'm.json').read_bytes()).hexdigest()
        (tmp_path / 'owner.json').write_text(json.dumps(s))
        st.owner_model = load_owner_model(tmp_path / 'owner.json')
    seen = []

    class Tracks:
        def update(self, tick, units, raw, own, info):
            seen.append(list(own)); return [[0.]*len(st.owner_model[0].names) for _ in units], [1]*len(units)
    st.owner_tracks = Tracks()
    st.public_events = [dict(tick=80, name='Knight', x=9., y=25., seat=0),
                        dict(tick=85, name='Goblins', x=3., y=20., seat=1)]
    st.own_deploys = [(80, 'Knight', 9., 25.), (90, 'Bats', 9., 12.)]          # Bats: dropped by the guard
    LiveTranslator.learned_owners(st, dict(tick=100, timestamp_ms=1, units=[unit(0, 9., 12., 'Bats')],
                                           units_yolo=['bat']))
    assert seen == [expect]


def test_badge_cue_history_over_visible_frames_only():
    """The badge classifier's P(opp) counts only in frames with a visible cue; a classifier-off record leaves the
    BADGE columns unknown (-1 / 0), and the v1 columns are unchanged by them."""
    from bot.live.owner_track import NAMES_V5, BADGE
    col = {n: NAMES_V5.index(n) for n in BADGE}
    a, b = OwnerTracks(_classes()), OwnerTracks(_classes(), names=NAMES_V5)
    seq = [dict(badge_p_opp=.9, badge_visible=.95), dict(badge_p_opp=.1, badge_visible=.2),   # 2nd: no visible cue
           dict(badge_p_opp=.7, badge_visible=.8)]
    for k, inf in enumerate(seq):
        us = [unit(1, 9., 25. - .2*k)]
        r1, _ = a.update(100 + 5*k, us, ['knight'], (), [inf])
        r2, _ = b.update(100 + 5*k, us, ['knight'], (), [inf])
        assert r2[0][:len(NAMES)] == r1[0]
    r = r2[0]
    assert r[col['badge_known']] == 1 and r[col['cur_badge_vis']] == .8 and r[col['cur_badge_opp']] == .7
    assert abs(r[col['mean_badge_opp']] - .8) < 1e-9 and r[col['n_badge_seen']] == 2
    assert abs(r[col['frac_badge_seen']] - 2/3) < 1e-9
    off, _ = OwnerTracks(_classes(), names=NAMES_V5).update(100, [unit(1, 9., 25.)], ['knight'], (), [dict(p_team=.9)])
    assert [off[0][col[n]] for n in BADGE] == [0., -1., -1., -1., -1., 0., 0.]


def test_card_match_keeps_the_track_across_raw_classes_of_one_card():
    """v1.4d (`track_match: card`): a body whose raw class flips bat -> bat-evolution continues its track (history,
    frac_opp); with the default raw-class match it starts a fresh track, as before."""
    col = NAMES.index('n_obs')
    for match, n_obs in (('raw', 1.), ('card', 4.)):
        tr = OwnerTracks(_classes(), match=match)
        for k, raw in enumerate(['bat', 'bat', 'bat', 'bat-evolution']):
            rows, _ = tr.update(100 + 5*k, [unit(0 if k < 3 else 1, 3.4, 22.4 + .2*k, 'Bats')], [raw])
        assert rows[0][col] == n_obs
    import pytest as _p
    with _p.raises(ValueError):
        OwnerTracks(_classes(), match='nope')


def test_a_badge_owner_model_fails_closed_without_the_classifier(tmp_path):
    from bot.live.owner_track import NAMES_V5
    from bot.live.translate import LiveTranslator, load_owner_model
    st = Stub(tmp_path)                                    # (writes the v1 stand-in first)
    m = frac_model(); m['names'] = list(NAMES_V5); m.pop('sha')
    (tmp_path / 'm.json').write_text(json.dumps(m))
    s = dict(model='m.json', sha256=hashlib.sha256((tmp_path / 'm.json').read_bytes()).hexdigest(), classes=str(CLASSES),
             classes_sha256=hashlib.sha256(CLASSES.read_bytes()).hexdigest(), theta=.5, badge_model='398562c523d58374')
    (tmp_path / 'owner.json').write_text(json.dumps(s))
    st.owner_model = load_owner_model(tmp_path / 'owner.json')
    st.owner_tracks = OwnerTracks(st.owner_model[2], OWN, tuple(st.owner_model[0].names))
    st.own_deploys = []
    rec = lambda t, b: dict(tick=t, timestamp_ms=t, units=[unit(0, 9., 12., 'Bats')], units_yolo=['bat'],
                            units_yolo_info=[dict(p_team=.1, **({'badge_model': b, 'badge_visible': .9, 'badge_p_opp': .1}
                                                                if b else {}))])
    with pytest.raises(RuntimeError, match='badge classifier'):
        LiveTranslator.learned_owners(st, rec(100, None))
    st._badge_checked = False
    LiveTranslator.learned_owners(st, rec(105, '398562c523d58374'))
    LiveTranslator.learned_owners(st, rec(110, None))                     # later gaps are counted, not fatal
    assert st.stats['owner_badge_missing'] == 1
