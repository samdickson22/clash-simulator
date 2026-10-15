"""LIVE glue tests (player, translator, belief, session, replay guards).

    PYTHONPATH=. CLASHER_BOT_RUNTIME=... CLASHER_LIVE_FAST=student:<it5s2.pt>@0.5375 \
        nice -n 19 taskset -c 2-6 python -m pytest -q bot/live/test_live.py

Needs the frozen runtime (~15 s setup) and the it5s2 checkpoint; a few short games in our engine (~3 min, 5 cores).
"""
import copy
import json

import numpy as np
import pytest

BASE = 1455777415631152 + 10**6     # fresh cases (not the HEADLINE bank)


@pytest.fixture(scope='module')
def rt():
    from bot.players.runtime import Runtime
    return Runtime()


def short_game(rt, name, *, index=3, ticks=700, opponent='v1'):
    from bot.players.ours import play_match, x4s_setup
    from bot.live.player import make_live_player
    case = x4s_setup(rt, index, BASE)
    bot = make_live_player(rt, name)
    res = play_match(rt, {case['seat']: bot, 1-case['seat']: make_live_player(rt, opponent)},
                     seed=case['seed'], decks=case['decks'], max_ticks=ticks)
    return res, bot, case


# -- player -----------------------------------------------------------------------------------------------------
def test_unbounded_wall_player_is_k4c_r16(rt):
    a, _, _ = short_game(rt, 'K4C-r16')
    b, _, _ = short_game(rt, 'K4CW-r16')
    assert a['command_sha256'] == b['command_sha256']


def test_fast_tier_is_the_it5s2_student(rt):
    from bot.live.player import FAST_DEFAULT
    a, _, _ = short_game(rt, FAST_DEFAULT)
    b, bot, _ = short_game(rt, 'LIVE-fast-it5s2')
    assert a['command_sha256'] == b['command_sha256']
    assert {d['source'] for d in bot.decisions} == {'fast'}


def test_wall_deadline_is_kept(rt):
    res, bot, case = short_game(rt, 'LIVE-K4CW-r16-w120-t4', ticks=900)
    searched = [d for d in bot.decisions if 'search_wall_ms' in d]
    assert searched
    walls = sorted(d['wall_ms'] for d in searched)
    assert walls[len(walls)//2] < 120 and walls[-1] < 160, walls[-5:]
    assert {d['source'] for d in searched} <= {'search', 'default-it5s2'}


def test_search_error_falls_back_to_it5s2_then_disables(rt):
    from bot.live.player import LivePlayer
    bot = LivePlayer(rt, tier='search', wall_ms=150, threads=1, max_errors=2)

    def boom(*a, **k):
        raise RuntimeError('injected')
    bot.search.act = boom
    _play_with(rt, bot)
    srcs = [d['source'] for d in bot.decisions]
    assert srcs[:2] == ['fast-error', 'fast-error'] and set(srcs[2:]) <= {'fast-disabled'}
    assert all(d['action'] == d['fast_action'] for d in bot.decisions)


def _play_with(rt, bot, index=3, ticks=500):
    from bot.players.ours import play_match, x4s_setup
    from bot.live.player import make_live_player
    case = x4s_setup(rt, index, BASE)
    res = play_match(rt, {case['seat']: bot, 1-case['seat']: make_live_player(rt, 'v1')},
                     seed=case['seed'], decks=case['decks'], max_ticks=ticks)
    return res, bot, case


def test_wall_name_parse():
    from bot.live.player import parse_wall_name, wall_name
    assert parse_wall_name('K4CW-r16-w200-t4') == dict(r3a=16, wall_ms=200, threads=4)
    assert parse_wall_name('K4CW-r16') == dict(r3a=16, wall_ms=None, threads=1)
    assert wall_name(16, 150, 4) == 'K4CW-r16-w150-t4'


# -- belief -----------------------------------------------------------------------------------------------------
def test_live_belief_survives_off_prior_decks(rt):
    from fair_player import PublicPlanner
    from derived_public_state import PublicEvent
    from bot.live.player import live_belief_class, completed_prior
    p = PublicPlanner(rt.R, rt.PRIOR, 1)
    b = p.belief
    b.__class__ = live_belief_class()
    b.human_prior = rt.PRIOR
    deck = ['Golem', 'Xbow', 'Rocket', 'GoblinBarrel', 'Lightning', 'Tornado', 'MightyMiner', 'Goblinstein']
    events = [PublicEvent(200 + 40*i, 'card', c) for i, c in enumerate(deck[:6])]
    b.update(500, events)
    assert b.rebuilds >= 1
    s = b.sample(np.random.default_rng(0))
    assert set(c for c in s['hand'] + s['cycle'] if c) >= set(deck[:6]) - {None}
    pr = completed_prior(rt.PRIOR, deck[:3])
    assert all(set(deck[:3]) <= set(d['cards']) and len(set(d['cards'])) == 8 for d in pr['decks'])


# -- translator -------------------------------------------------------------------------------------------------
OWN = ['Knight', 'Archers', 'Giant', 'Musketeer', 'MiniPekka', 'Fireball', 'Arrows', 'Goblins']


def record(tick=600, **kw):
    r = dict(tick=tick, elixir=5.0, hand=dict(cards=OWN[:4], next=OWN[4]),
             units=[{'class': 'Knight', 'owner': 0, 'x': 4.5, 'y': 10.5, 'hp_frac': .5, 'score': .9},
                    {'class': 'HogRider', 'owner': 1, 'x': 3.5, 'y': 18.0, 'hp_abs': 400, 'score': .9},
                    {'class': 'NotABody', 'owner': 1, 'x': 3.5, 'y': 18.0, 'hp_frac': 1., 'score': .9}],
             towers=[dict(owner=0, kind='princess', side='left', hp_frac=.5, alive=True),
                     dict(owner=1, kind='princess', side='left', hp_frac=0., alive=False)],
             events=[dict(owner=1, card='HogRider', x=3.5, y=19.5, tick=560),
                     dict(owner=0, card='Knight', x=9, y=20, tick=500)])
    r.update(kw)
    return r


def rows(packet, rt):
    o = packet.observation
    names = rt.R.builder.token_names
    return [dict(name=names[int(o.entity_ids[i])], kind=int(np.argmax(f[4:9])), own=bool(f[2] > .5),
                 x=float(f[0])*18, y=float(f[1])*32, hp=float(f[9]))
            for i, f in ((i, o.entity_features[i]) for i in np.flatnonzero(o.entity_mask))]


def test_translator_rows_towers_globals(rt):
    from bot.live.translate import LiveTranslator
    tr = LiveTranslator(rt, OWN, plays_from='events')
    info = tr.information(record())
    r = rows(info.packet, rt)
    k = [x for x in r if x['name'] == 'Knight'][0]
    assert k['own'] and k['kind'] == 0 and (k['x'], k['y']) == pytest.approx((4.5, 10.5), abs=1e-4) and k['hp'] == pytest.approx(.5)
    hog = [x for x in r if x['name'] == 'HogRider'][0]
    assert not hog['own'] and 0 < hog['hp'] < 1
    assert tr.stats['unmapped_card_unit:NotABody'] == 1
    towers = [x for x in r if x['name'] in ('KingTower', 'Tower')]
    assert len(towers) == 5                                            # enemy left princess destroyed
    assert not any(not x['own'] and x['x'] < 9 and x['name'] == 'Tower' for x in towers)
    g = info.packet.observation.global_features
    assert g[8] == pytest.approx(.5) and g[9] == 1 and g[11] == 0 and g[12] == 1
    assert g[7] == 0                                                   # crowns: v5 may zero col 6/7
    assert g[5] == pytest.approx(.5)
    assert [e.name for e in info.events] == ['HogRider']
    assert info.packet.observation.own_last_play.card_name == 'Knight'
    # Our Knight was played at 500 (own event): by 600 the engine refilled its slot with MiniPekka and Knight waits
    # at the back of the cycle. The record's stale HUD (Knight still held) is overridden by the tracked state.
    assert info.own['hand'] == ['MiniPekka', 'Archers', 'Giant', 'Musketeer']
    assert info.own['cycle'] == ['Fireball', 'Arrows', 'Goblins', 'Knight']
    assert tr.stats['own_fix:slot'] == 1 and tr.stats['own_fix:next_in_hand'] == 1


def test_translator_equals_true_packet_on_engine_view(rt):
    """A perfect record of our engine's true view reproduces the v5 packet except unit facing and
    spell/projectile rows (not in the perception schema)."""
    from bot.players.ours import play_match, x4s_setup
    from bot.live.player import make_live_player
    from bot.live.synth import SynthPerception
    from bot.live.translate import LiveTranslator
    case = x4s_setup(rt, 0, BASE)
    decks = case['decks'] if case['seat'] == 0 else case['decks'][::-1]
    bad = []

    class Probe:
        name, deadline_seconds = 'probe', None

        def __init__(self):
            self.inner, self.tr = make_live_player(rt, 'v1'), LiveTranslator(rt, decks[0], plays_from='events')
            self.synth = SynthPerception(rt)

        def start(self, ctx):
            self.inner.start(ctx)
            self.tr.set_own_order(ctx.own_order)

        def act(self, view):
            info = self.tr.information(self.synth.record(view))
            a, b = view.info.packet.observation, info.packet.observation
            for f in ('hand_ids', 'global_features', 'opponent_history_ids', 'opponent_history_ages',
                      'opponent_seen_card_ids'):
                if not np.allclose(getattr(a, f), getattr(b, f), atol=1e-5):
                    bad.append((view.tick, f))
            ta = sorted((int(t), round(float(r[0]), 4), round(float(r[1]), 4), round(float(r[9]), 4))
                        for t, r in zip(a.entity_ids[a.entity_mask], a.entity_features[a.entity_mask])
                        if np.argmax(r[4:9]) < 2)
            tb = sorted((int(t), round(float(r[0]), 4), round(float(r[1]), 4), round(float(r[9]), 4))
                        for t, r in zip(b.entity_ids[b.entity_mask], b.entity_features[b.entity_mask]))
            if ta != tb:
                bad.append((view.tick, 'rows'))
            return self.inner.act(view)

        def close(self):
            pass
    play_match(rt, {0: Probe(), 1: make_live_player(rt, 'v1')}, seed=case['seed'], decks=decks, max_ticks=1500)
    assert not bad, bad[:5]


def test_invariance_opponent_private_fields_never_enter(rt):
    """Fair information: the record schema has no opponent-HUD input; extra opponent-private keys are ignored,
    and the only enemy-card channel is the accepted public play stream."""
    from bot.live.translate import LiveTranslator
    a = LiveTranslator(rt, OWN).information(record())
    poisoned = record(opponent=dict(hand=['Golem'] * 4, elixir=9.9, next='Rocket', deck=['Xbow'] * 8),
                      opp_elixir=0.1, opp_hand=['Zap'] * 4)
    for u in poisoned['units']:
        u['private_card_id'] = 26000000
    b = LiveTranslator(rt, OWN).information(poisoned)
    for f in ('entity_ids', 'entity_features', 'hand_ids', 'global_features', 'opponent_history_ids',
              'opponent_seen_card_ids', 'entity_levels'):
        assert np.array_equal(getattr(a.packet.observation, f), getattr(b.packet.observation, f)), f
    assert a.events == b.events and a.own == b.own


def test_t1_records_read_only_the_own_hud(rt, tmp_path, monkeypatch):
    """T1 source: poisoning the OPPONENT's evaluation-only record changes nothing in our records."""
    import gzip
    import shutil
    from bot.live import replay
    path, entry = replay.t1_matches()[0]
    dst = tmp_path / path.name
    shutil.copytree(path, dst)
    lines = []
    with gzip.open(dst / 'evaluation-only.jsonl.gz', 'rt') as f:
        for line in f:
            r = json.loads(line)
            for p in r['observation']['players']:
                if p['owner'] == 1:
                    p['elixir'], p['hand'] = 0.0, list(reversed(p['hand']))
            lines.append(json.dumps(r))
    with gzip.open(dst / 'evaluation-only.jsonl.gz', 'wt') as f:
        f.write('\n'.join(lines) + '\n')
    a = list(replay.T1Match(rt, path, entry, 0).records())[:200]
    b = list(replay.T1Match(rt, dst, entry, 0).records())[:200]
    assert a == b


def test_t1_split_guard_refuses_unregistered_dirs(tmp_path):
    from bot.live import replay
    (tmp_path / 'v4-phase-a-1975100700').mkdir()
    (tmp_path / 'heldout-episode').mkdir()
    with pytest.raises(AssertionError):
        replay.t1_matches(root=tmp_path)
    split = json.loads((replay.DATA / 't1-split.json').read_text())
    held = [m['episode'] for m in split['matches'] if m['split'] not in replay.SPLIT_OK][:1]
    if held:
        (tmp_path / 'heldout-episode').rmdir()
        (tmp_path / held[0]).mkdir()
        with pytest.raises(AssertionError):
            replay.t1_matches(root=tmp_path)


def test_non_c56_cards_drop_or_proxy_and_ninth_card(rt):
    from bot.live.translate import LiveTranslator
    ev = [dict(owner=1, card='SpearGoblins', x=3, y=20, tick=300)]
    tr = LiveTranslator(rt, OWN, plays_from='events')
    info = tr.information(record(events=ev, units=[]))
    assert info.events == () and tr.stats['dropped_card:SpearGoblins'] == 1
    tr = LiveTranslator(rt, OWN, unknown_card='proxy', plays_from='events')
    info = tr.information(record(events=ev, units=[]))
    assert [e.name for e in info.events] == ['Goblins']
    cards = ['Knight', 'Archers', 'Giant', 'Musketeer', 'MiniPekka', 'Fireball', 'Arrows', 'Goblins', 'Zap']
    tr = LiveTranslator(rt, OWN, plays_from='events')
    info = tr.information(record(tick=900, units=[], events=[dict(owner=1, card=c, x=3, y=20, tick=100+50*i)
                                                   for i, c in enumerate(cards)]))
    assert len(info.events) == 8
    assert tr.stats['ninth_enemy_card_dropped'] + tr.stats['cycle_conflict_dropped:1'] == 1


def test_stream_guard_keeps_trackers_alive_after_a_missed_play(rt):
    """A missed enemy play leaves a card 'still cycling' in the D1 trackers; its next real play is dropped, not
    allowed to raise inside the players' pollers/belief."""
    from bot.live.translate import LiveTranslator
    from imitation.evaluation.d1 import DerivedD1, PublicEvent
    seq = ['Knight', 'Archers', 'Giant', 'Musketeer', 'MiniPekka', 'Knight']      # 4 plays later Knight is back
    tr = LiveTranslator(rt, OWN, plays_from='events')
    info = None
    for i, c in enumerate(seq):
        if i == 2:
            continue                                                                # perception missed Giant
        info = tr.information(record(tick=200+60*i, units=[], events=[dict(owner=1, card=c, x=3, y=20, tick=180+60*i)]))
    d1 = DerivedD1(rt.R.costs)
    for e in tr.public_events:
        d1.accept(PublicEvent(e['tick'], 'card', e['name'], 0., e['x'], e['y']))      # must not raise
    assert tr.stats['cycle_conflict_dropped:1'] == 1 and [e.name for e in info.events][-1] == 'MiniPekka'


def test_late_events_never_go_behind_the_previous_record(rt):
    from bot.live.translate import LiveTranslator
    tr = LiveTranslator(rt, OWN, plays_from='events')
    tr.information(record(tick=600, events=[], units=[]))
    info = tr.information(record(tick=610, units=[], events=[dict(owner=1, card='Zap', x=3, y=20, tick=590)]))
    assert info.events[-1].tick == 600 and tr.stats['late_event_retimed'] == 1


def test_tick_from_clock():
    from bot.live.translate import tick_from_clock
    assert tick_from_clock(180, 'regular') == 0 and tick_from_clock(60, 'regular') == 2400
    assert tick_from_clock(120, 'overtime') == 3600 and tick_from_clock(0, 'overtime') == 6000


# -- session ----------------------------------------------------------------------------------------------------
def test_live_session_runs_and_reserves(rt):
    from bot.live.player import LivePlayer
    from bot.live.translate import LiveSession
    s = LiveSession(rt, LivePlayer(rt, tier='fast'), OWN, seed=7)
    out = []
    for tick in range(88, 400, 3):
        r = record(tick=tick, events=[], elixir=min(10., 5 + tick/56))
        d = s.step(r)
        if d is not None:
            out.append(d)
    assert out and all(d.action == 2304 or 0 <= d.action < 2304 for d in out)
    plays = [d for d in out if d.action < 2304]
    if plays:   # a submitted play reserves its slot: no second play while it is pending
        assert s.ch.submitted >= 1
    s.close()


# -- levels -----------------------------------------------------------------------------------------------------
def test_level_root_is_the_frozen_root_at_level_11_and_scales_otherwise(rt, monkeypatch):
    import fair_player
    from bot.live.levels import LevelRoot, Levels
    from bot.live.translate import LiveTranslator
    info = LiveTranslator(rt, OWN).information(record())
    opp = dict(elixir=5.0, hand=['Knight', 'Archers', 'Giant', 'Musketeer'],
               cycle=['MiniPekka', 'Fireball', 'Arrows', 'Goblins'], refill=0)
    captured = []
    monkeypatch.setattr(fair_player.clasher_core, 'BattleState', lambda payload: captured.append(payload))
    rt.R.root(info, opp, np.random.default_rng(5))
    lr = LevelRoot(rt.R, Levels(own_tower=13, own=11, opp=9, opp_bodies={'HogRider': 7}))
    assert LevelRoot(rt.R, Levels()).payload(info, opp, np.random.default_rng(5)) == captured[0]
    scaled = json.loads(lr.payload(info, opp, np.random.default_rng(5)))
    base = json.loads(captured[0])
    by = lambda p: {(e['stats']['name'], e['owner'], round(e['x'], 3)): e for e in p['entities']}
    a, b = by(base), by(scaled)
    for k, e in a.items():
        name, owner, _ = k
        if name == 'Knight':
            assert b[k]['stats']['max_hp'] == e['stats']['max_hp'] and b[k]['hp'] == e['hp']
        if name == 'HogRider':
            assert b[k]['stats']['max_hp'] < e['stats']['max_hp'] and b[k]['stats']['damage'] < e['stats']['damage']
        if name in ('Tower', 'KingTower') and owner == 0:
            assert b[k]['stats']['max_hp'] > e['stats']['max_hp']


# -- perception schema v1: clock, births, real frame_record code path ------------------------------------------------
def test_clock_tracker_matches_the_hud_convention():
    from bot.live.births import ClockTracker
    from bot.live.synth import hud_clock
    c, worst = ClockTracker(), 0
    for tick in range(1, 6001, 3):                    # ~frames every 150 ms
        clock, phase = hud_clock(tick)
        worst = max(worst, abs(c(clock, phase, 50*tick) - tick))
    assert worst <= 10, worst                      # centre of the displayed second until a phase anchor


def test_births_derive_plays_and_ignore_children_flicker_and_own(rt):
    from bot.live.translate import LiveTranslator
    tr = LiveTranslator(rt, OWN)
    seq = {
        600: [('Knight', 1, 9.5, 24.5)],                                  # opponent plays Knight
        610: [],                                                          # missed detection (flicker)
        620: [('Knight', 1, 9.5, 23.8)],                                  # same Knight, not a play
        630: [('Knight', 1, 9.5, 23.4), ('GoblinHut', 1, 4.5, 26.5)],     # GoblinHut play
        635: [('GoblinHut', 1, 4.5, 26.5), ('Valkyrie', 1, 14.0, 26.0)],  # Valkyrie: one-frame mislabel
        700: [('Knight', 1, 9.5, 20.0), ('GoblinHut', 1, 4.5, 26.5), ('GoblinHut', 1, 4.0, 25.0)],  # hut child
        705: [('GoblinHut', 1, 4.5, 26.5), ('GoblinHut', 1, 4.0, 24.8)],
        710: [('Knight', 0, 4.5, 8.5)],                                   # our own unit: not an opponent play
        715: [('Knight', 0, 4.5, 8.8)],
        720: [('Archers', 1, 9.0, 12.0)],                                 # opponent unit on OUR side: not a play
        725: [('Archers', 1, 9.0, 11.8)],
    }
    info = None
    for tick, units in seq.items():
        info = tr.information(record(tick=tick, events=[], units=[
            {'cls': c, 'card': c, 'owner': o, 'x': x, 'y': y, 'hp_frac': 1., 'score': .9} for c, o, x, y in units]))
    # confirmed on the 2nd sighting; first-sighting tick, floored to the previous record (the belief cannot go back)
    assert [(e.name, e.tick) for e in info.events] == [('Knight', 610), ('GoblinHut', 635)]
    r = rows(info.packet, rt)
    assert tr.tracker.stats['birth_outside_zone'] == 1 and tr.tracker.stats['unconfirmed_birth'] == 1


def test_real_frame_record_code_path(rt):
    """A record made by the perception owner's own frame_record() (live/perception/common.py) translates."""
    import importlib
    import sys
    saved = list(sys.path)
    try:
        C = importlib.import_module('live.perception.common')
    finally:
        sys.path[:] = saved
    dec = dict(units=[dict(identity='Knight', owner=1, x=4.5, y=29-10.5, score=.9, hp_frac=.5),      # ours (native 1)
                      dict(identity='HogRider', owner=0, x=14.0, y=32-25.0, score=.8, hp_frac=None),  # theirs
                      dict(identity='KingTower', owner=1, x=9, y=29, score=.99, hp_frac=1.)],
               towers=[dict(owner=o, kind=k, side=sd, score=.99, hp_frac=.75) for o, k, sd, _, _ in C.TOWER_SLOTS],
               hand=['Knight', 'Archers', 'Giant', 'Musketeer'], next='MiniPekka', hand_prob=[.99]*5,
               elixir=5.5, clock=150.4, phase=1)
    rec = C.frame_record(dec, timestamp_ms=123456)
    assert rec['schema'] == 'clasher.live.perception-frame.v1'
    from bot.live.translate import LiveTranslator
    tr = LiveTranslator(rt, OWN)
    info = tr.information(rec)
    assert 601 <= info.tick <= 620 and info.events == ()              # a birth needs a second sighting
    for k in range(1, 5):                                              # 4 more frames, 5 ticks apart
        info = tr.information(C.frame_record(dict(dec, clock=150.4 - .25*k), timestamp_ms=123456 + 250*k))
    assert 621 <= info.tick <= 640
    r = rows(info.packet, rt)
    k = [x for x in r if x['name'] == 'Knight'][0]
    assert k['own'] and (k['x'], k['y']) == pytest.approx((4.5, 32-(29-10.5)), abs=1e-3) and k['hp'] == pytest.approx(.5)
    h = [x for x in r if x['name'] == 'HogRider'][0]
    assert not h['own'] and h['hp'] == pytest.approx(1.) and (h['x'], h['y']) == pytest.approx((14.0, 25.0), abs=1e-3)
    assert len([x for x in r if x['name'] in ('KingTower', 'Tower')]) == 6
    assert [e.name for e in info.events] == ['HogRider']                 # opponent play from its birth
    g = info.packet.observation.global_features
    assert g[5] == pytest.approx(.55) and g[8] == pytest.approx(.75)


def test_perc_player_runs_in_both_seats(rt):
    """PERC-<arm>:<player> plays our engine through synthetic perception + translator; seat 1 frames are rotated."""
    for index in (0, 1):
        res, bot, case = short_game(rt, 'PERC-p42:LIVE-fast-it5s2', index=index, ticks=900)
        assert bot.errors == 0 and res['plays'][case['seat']] > 0
    a, _, _ = short_game(rt, 'LIVE-fast-it5s2', index=1, ticks=400)
    b, _, _ = short_game(rt, 'PERC-events:LIVE-fast-it5s2', index=1, ticks=400)
    assert a['plays'] == b['plays']


SAMPLE_RECORDS = '/mpac/sdicks02/jobs/clasher/live-perception-20261014/sample-records'


@pytest.mark.skipif(not __import__('os').path.isdir(SAMPLE_RECORDS), reason='no real perception records dropped yet')
def test_real_perception_records_translate(rt):
    """Real LivePerception output (validation match; lines {episode, seq, tick, pred, truth}, perception owner
    2026-10-15) translates without the line's tick (HUD clock only), with no unmapped card, and yields opponent
    plays from births that match the true plays."""
    import glob
    from bot.live.translate import LiveTranslator
    from bot.live.real_records import unique_plays, match_plays
    path = sorted(glob.glob(SAMPLE_RECORDS + '/*.jsonl'))[0]
    rows = [json.loads(l) for l in open(path) if l.strip()][:600]
    assert rows[0]['pred']['schema'] == 'clasher.live.perception-frame.v1'
    deck = list(dict.fromkeys(c for r in rows for c in r['truth']['hand']['cards'] + [r['truth']['hand']['next']] if c))
    tr = LiveTranslator(rt, (deck + [c for c in OWN if c not in deck])[:8])
    for r in rows:
        info = tr.information(r['pred'])                  # no 'tick' key: HUD clock + phase + timestamp
        assert info.packet.observation.entity_mask.sum() >= 1
    assert not any(k.startswith(('unmapped_card_unit', 'no_template')) for k in tr.stats), dict(tr.stats)
    # play derivation, timed by the true tick (the clock is scored separately: test_clock_tracker_*)
    tr = LiveTranslator(rt, (deck + [c for c in OWN if c not in deck])[:8])
    for r in rows:
        tr.information(dict(r['pred'], tick=int(r['tick']), events=[]))
    derived = [dict(owner=o, card=c, x=x, y=y, tick=t) for o, c, x, y, t in tr.derived_plays]
    m = match_plays(derived, unique_plays(rows))
    assert m['recall'] >= .6 and m['precision'] >= .6, m


def test_perception_event_times_in_ms_are_converted(rt):
    """frame_record events carry the estimated execution time in ms: 'exec_ms' (frame_record) or 'tick' in ms with
    a 'score' (sample-records). Both become ticks relative to the record's timestamp."""
    from bot.live.translate import LiveTranslator
    for ev in (dict(owner=1, card='Knight', x=9.5, y=24.5, exec_ms=600*50 - 1000, score=.9),
               dict(owner=1, card='Knight', x=9.5, y=24.5, tick=600*50 - 1000, score=.9)):
        tr = LiveTranslator(rt, OWN, plays_from='events')
        info = tr.information(record(tick=600, timestamp_ms=600*50, units=[], events=[ev]))
        assert [(e.name, e.tick) for e in info.events] == [('Knight', 580)], ev
