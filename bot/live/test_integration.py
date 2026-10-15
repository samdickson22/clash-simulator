"""LIVE integration tests: event-card fusion (live/perception/events.py), real-record replay glue
(bot/live/real_replay.py), LiveSession poll gaps, empirical noise channel.

    PYTHONPATH=. CLASHER_BOT_RUNTIME=... CLASHER_LIVE_FAST=student:<it5s2.pt>@0.5375 \
        nice -n 19 taskset -c 2-5 python -m pytest -q bot/live/test_integration.py

The fusion tests need only torch. The real-record test needs the validation dump
(/mpac/sdicks02/jobs/clasher/live-integration-20261015/dump) and the T1 recordings; it is skipped without them.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

PERCEPTION = Path(__file__).resolve().parents[2] / 'live/perception'
sys.path.insert(0, str(PERCEPTION))
CARDS = ['Knight', 'Valkyrie', 'Zap', 'Fireball', 'HogRider']
DUMP = Path('/mpac/sdicks02/jobs/clasher/live-integration-20261015/dump')


# -- event fusion ---------------------------------------------------------------------------------------------
def _peak(side, x, y, e, probs, age=0.):
    import torch
    return (side, x, y, e, torch.tensor(probs, dtype=torch.float32), age)


def _run(tr, frames):
    """frames: [(ts, peaks, units)] -> [(ts, emitted event)]"""
    out = []
    for ts, pk, units in frames:
        for e in tr.update(None, ts, peaks=pk, units=units):
            out.append((ts, e))
    return out


def _unit(card, x, y_native, score=.8, owner=1):
    """Record-frame unit (owner 0 = us; record y = 32 - native y). Opponent = native side 0."""
    return dict(card=card, owner=owner, x=x, y=32.-y_native, score=score)


# The event head says Knight (0.5) over Valkyrie (0.4) at an opponent play at native (5, 10).
HEAD = [.5, .4, .02, .02, .02]


def _frames(units_after, units_before=(), n=12):
    fr = []
    for k in range(n):
        ts = 1000. + 100*k
        pk = [_peak(0, 5., 10., .7, HEAD, age=ts-1000.)] if 1 <= k <= 4 else []
        fr.append((ts, pk, list(units_before) if ts < 1000 else list(units_after) if k >= 1 else list(units_before)))
    return [(500. + 100*j, [], list(units_before)) for j in range(5)] + fr


def test_hold_zero_is_the_original_tracker():
    from events import EventTracker
    out = _run(EventTracker(CARDS, threshold=.6), _frames([_unit('Valkyrie', 5., 10.)]))
    assert len(out) == 1 and out[0][1]['card'] == 'Knight' and out[0][0] == 1100.      # first crossing frame, head card


def test_newborn_body_revises_the_card_and_emits_once():
    from events import EventTracker
    tr = EventTracker(CARDS, threshold=.6, hold_ms=500., max_hold_ms=500., vote_min=.3, agree_frames=0)
    out = _run(tr, _frames([_unit('Valkyrie', 5.5, 10.2)]))
    assert len(out) == 1, out
    ts, e = out[0]
    assert e['card'] == 'Valkyrie' and e['head_card'] == 'Knight' and tr.revised == 1
    assert ts >= e['execution_timestamp_ms'] + 500 - 1e-6                               # held until exec + hold


def test_pre_existing_unit_is_no_evidence():
    from events import EventTracker
    v = _unit('Valkyrie', 5.5, 10.2)
    tr = EventTracker(CARDS, threshold=.6, hold_ms=500., max_hold_ms=500., vote_min=.3, agree_frames=0)
    out = _run(tr, _frames([v], units_before=[v]))
    assert [e['card'] for _, e in out] == ['Knight'] and tr.revised == 0


def test_far_or_own_units_do_not_vote_and_agreement_emits_early():
    from events import EventTracker
    far, own = _unit('Valkyrie', 12., 10.), _unit('Valkyrie', 5., 10., owner=0)
    tr = EventTracker(CARDS, threshold=.6, hold_ms=500., max_hold_ms=500., vote_min=.3, agree_frames=0)
    assert [e['card'] for _, e in _run(tr, _frames([far, own]))] == ['Knight']
    tr = EventTracker(CARDS, threshold=.6, hold_ms=800., max_hold_ms=800., vote_min=.3, agree_frames=2)
    out = _run(tr, _frames([_unit('Knight', 5., 10.)]))
    assert len(out) == 1 and out[0][1]['card'] == 'Knight' and out[0][0] < out[0][1]['execution_timestamp_ms'] + 800


def test_confident_bodyless_spell_emits_at_the_crossing():
    from events import EventTracker
    spell = [.02, .02, .9, .03, .03]
    fr = [(1000. + 100*k, [_peak(0, 5., 10., .7, spell, age=100.*k)] if k < 3 else [], []) for k in range(12)]
    out = _run(EventTracker(CARDS, threshold=.6, hold_ms=700., max_hold_ms=700., early_share=.6), fr)
    assert len(out) == 1 and out[0][1]['card'] == 'Zap' and out[0][0] == 1000.
    out = _run(EventTracker(CARDS, threshold=.6, hold_ms=700., max_hold_ms=700.), fr)
    assert len(out) == 1 and out[0][0] >= 1700.


# -- translator / session (frozen runtime) ------------------------------------------------------------------------
@pytest.fixture(scope='module')
def rt():
    from bot.players.runtime import Runtime
    return Runtime()


def test_both_translator_counts_one_play_from_event_and_birth(rt):
    from bot.live.real_replay import BothTranslator
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_live import OWN, record
    tr = BothTranslator(rt, OWN)
    tr.set_own_order(OWN)
    ev = [dict(owner=1, card='HogRider', x=3.5, y=19.0, tick=598, tick_unit='tick')]
    units = [{'card': 'HogRider', 'owner': 1, 'x': 3.5, 'y': 19.0, 'hp_frac': 1., 'score': .9}]
    for k, t in enumerate(range(600, 660, 5)):
        tr.information(record(tick=t, units=units, events=ev if k == 0 else []))
    assert [n for _, n in tr.plays[1]] == ['HogRider'], (tr.plays, dict(tr.stats))
    for k, t in enumerate(range(660, 700, 5)):       # re-sent rows of a cumulative stream are not duplicates
        tr.information(record(tick=t, units=units, events=ev))
    assert sum(v for k, v in tr.stats.items() if k.startswith('both_duplicate')) <= 1


def test_ms_event_times_become_ticks(rt):
    """Perception schema v1: event tick = execution time in ms on the caller's timestamp clock."""
    from bot.live.translate import LiveTranslator
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_live import OWN, record
    tr = LiveTranslator(rt, OWN, plays_from='events')
    tr.set_own_order(OWN)
    r = record(tick=600, timestamp_ms=123_000., events=[dict(owner=1, card='HogRider', x=3.5, y=19.5, tick=122_000., score=.8)],
               event_tick_unit='ms on the caller timestamp clock (estimated execution time)')
    tr.information(r)
    assert tr.plays[1] == [(580, 'HogRider')]


def test_live_session_catches_up_skipped_polls(rt):
    """A frame gap > 250 ms skips a poll. The frozen 5-tick gate (imitation/evaluation/standalone.py) would raise on
    that and on every later poll; LiveSession catches up with can_act=False, so the fast tier keeps deciding."""
    from bot.live.player import LivePlayer
    from bot.live.translate import LiveSession
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_live import OWN, record
    s = LiveSession(rt, LivePlayer(rt, tier='fast'), OWN, seed=7)
    ticks = list(range(88, 300, 3)) + list(range(330, 500, 3))          # 300 -> 330: two polls skipped
    out = [d for d in (s.step(record(tick=t, events=[], elixir=min(10., 5 + t/56))) for t in ticks) if d is not None]
    srcs = [d.stats.get('source') for d in out if d.stats]
    assert s.tr.stats['catchup_polls'] >= 2 and 'fast-error' not in srcs, (dict(s.tr.stats), srcs[-5:])
    assert any(r.get('catch_up') for r in s.log) and not any(r.get('catch_up') and r['action'] < 2304 for r in s.log)
    s.close()


@pytest.mark.skipif(not DUMP.is_dir() or not any(DUMP.glob('*.jsonl.gz')), reason='validation dump not present')
def test_real_records_replay_end_to_end(rt, tmp_path):
    """Real LivePerception records of one validation match -> translators -> it5s2: no crash in any arm, the mirror
    puts perception units on the true units, and the play-event arm gets opponent plays to the bot."""
    import argparse
    from bot.live import real_replay as RR
    path = sorted(DUMP.glob('*.jsonl.gz'))[0]
    head, rows = RR.load_dump(path)
    assert head['split'] == 'validation'
    a = argparse.Namespace(tier='fast', wall_ms=None, threads=1, arms='ref,truth,births,fused,fused+births,fused-hud',
                           fusion=dict(RR.FUSION))
    cards = json.loads(Path('/mpac/sdicks02/jobs/clasher/live-perception-20261014/export-final/vocab.json').read_text())['cards']
    RR.run_match(rt, path, a, tmp_path, cards)
    m = json.loads((tmp_path/'matches.jsonl').read_text().splitlines()[0])
    assert all(v == 0 for v in m['errors'].values()) and all(v == 0 for v in m['decision_errors'].values()), m['errors']
    assert m['reach']['truth']['recall'] >= .9 and m['reach']['fused']['matched'] >= .5*m['true_opp_plays'], m['reach']
    rowsa = [json.loads(l) for l in (tmp_path/'agreement.jsonl').read_text().splitlines()]
    assert rowsa and sum(r['agree'] for r in rowsa if r['shadow'] == 'truth') >= .5*sum(r['shadow'] == 'truth' for r in rowsa)


def test_dump_guard_refuses_non_validation(tmp_path):
    import gzip
    from bot.live import real_replay as RR
    p = tmp_path/'x.jsonl.gz'
    with gzip.open(p, 'wt') as f:
        f.write(json.dumps(dict(episode='v4-phase-a-1975100708', split='heldout', truth_events=[]))+'\n')
    with pytest.raises(ValueError):
        RR.load_dump(p)
    split = tmp_path/'split.json'
    split.write_text(json.dumps(dict(matches=[dict(episode='E', split='validation')])))
    with pytest.raises(ValueError):            # not the registered split file
        RR.validation_entry('E', split)
    with pytest.raises(ValueError):            # registered split, but a heldout / unknown episode
        RR.validation_entry(next(m['episode'] for m in json.loads((RR.T1_DATA/'t1-split.json').read_text())['matches']
                                 if m['split'] == 'heldout'))


def test_empirical_channel_is_deterministic_and_keeps_own_plays():
    from bot.live.empirical import EmpiricalNoise, STATS
    if not STATS.exists():
        pytest.skip('empirical stats not fitted')
    stats = json.loads(STATS.read_text())
    rec = dict(tick=600, units=[dict(cls='Knight', card='Knight', owner=1, x=4., y=20., hp_frac=1., score=1.)]*3,
               towers=[dict(owner=0, kind='king', side='center', hp_frac=1., alive=True)],
               hand=dict(cards=['Knight', 'Archers', 'Giant', 'Musketeer'], next='MiniPekka'), elixir=5.,
               events=[dict(owner=0, card='Knight', x=4., y=5., tick=590), dict(owner=1, card='HogRider', x=4., y=20., tick=595)])
    deck = ['Knight', 'Archers', 'Giant', 'Musketeer', 'MiniPekka', 'Fireball', 'Arrows', 'Goblins']
    a = [EmpiricalNoise(stats, np.random.default_rng(1), deck)(dict(rec, tick=600 + 5*k)) for k in range(40)]
    b = [EmpiricalNoise(stats, np.random.default_rng(1), deck)(dict(rec, tick=600 + 5*k)) for k in range(40)]
    assert a == b
    assert all(any(e['owner'] == 0 and e['card'] == 'Knight' for e in r['events']) for r in a)
    opp = {(e['card'], e['tick']) for r in a for e in r['events'] if e['owner'] == 1}
    assert len(opp) <= 1 + sum(1 for r in a for e in r['events'] if e['owner'] == 1)   # each play decided once



def test_empirical_arm_names_and_ablations():
    from bot.live.perc import parse_empirical
    from bot.live.empirical import EmpiricalNoise, STATS
    assert parse_empirical('emp')[:2] == ('events', STATS) and parse_empirical('p42') is None
    src, path, ab = parse_empirical('emp-r2-both-xspell-xfp')
    assert (src, path.name, ab) == ('both', 'empirical-val-r2.json', frozenset({'spell', 'fp'}))
    with pytest.raises(ValueError):
        parse_empirical('emp-xnothing')
    assert parse_empirical('emp-sr1u50-xfp')[1].name == 'empirical-val-r1u50.json'
    if not STATS.exists():
        pytest.skip('empirical stats not fitted')
    stats = json.loads(STATS.read_text())
    rec = dict(tick=600, units=[dict(cls='Knight', card='Knight', owner=1, x=4.+k, y=20., hp_frac=.5, score=1.) for k in range(6)],
               towers=[dict(owner=0, kind='king', side='center', hp_frac=.7, alive=True)],
               hand=dict(cards=['Knight', 'Archers', 'Giant', 'Musketeer'], next='MiniPekka'), elixir=5.,
               events=[dict(owner=1, card='Zap', x=4., y=20., tick=590), dict(owner=1, card='HogRider', x=8., y=20., tick=595)])
    deck = ['Knight', 'Archers', 'Giant', 'Musketeer', 'MiniPekka', 'Fireball', 'Arrows', 'Goblins']
    ch = EmpiricalNoise(stats, np.random.default_rng(3), deck, ablate={'units', 'hud', 'ev'})
    for k in range(60):
        r = ch(dict(rec, tick=600 + 5*k))
        assert [(u['card'], u['x'], u['hp_frac']) for u in r['units']] == [(u['card'], u['x'], u['hp_frac']) for u in rec['units']]
        assert r['hand'] == rec['hand'] and r['elixir'] == 5. and r['towers'][0]['hp_frac'] == .7
        assert sorted((e['card'], e['tick']) for e in r['events']) == [('HogRider', 595), ('Zap', 590)]   # immediate, exact
    ch = EmpiricalNoise(stats, np.random.default_rng(3), deck, ablate={'spell'})
    for k in range(60):
        r = ch(dict(rec, tick=600 + 5*k))
        assert ('Zap', 590) in [(e['card'], e['tick']) for e in r['events']]
    with pytest.raises(ValueError):
        EmpiricalNoise(stats, np.random.default_rng(3), deck, ablate={'bogus'})

# -- resync-capable cycle tracking (bot/live/resync.py) -------------------------------------------------------------
DECK8 = ['Knight', 'Archers', 'Giant', 'Musketeer', 'MiniPekka', 'Fireball', 'Arrows', 'Goblins']   # opponent plays these
SEEN = [(100 + 40*i, c) for i, c in enumerate(DECK8)]              # all 8 revealed; queue = last 4, hand = first 4
MISSED = [(420, 'Knight'), (460, 'Archers')]                         # real plays perception missed
CONFLICT = (500, 'MiniPekka')                                        # legal after the misses; the mirror still queues it


def _feed(tr, extra=None, upto=520):
    from test_live import OWN, record
    plays = SEEN + [CONFLICT]
    for t in range(95, upto, 5):
        ev = [dict(owner=1, card=c, x=9., y=24., tick=pt, tick_unit='tick') for pt, c in plays if t - 5 < pt <= t]
        r = record(tick=t, units=[], events=ev)
        if extra:
            r.update(extra)
        tr.information(r)
    return tr


def test_plain_translator_drops_the_play_resync_infers_the_missed_ones(rt):
    from bot.live.translate import LiveTranslator
    from bot.live.resync import ResyncTranslator
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_live import OWN
    plain = LiveTranslator(rt, OWN, plays_from='events'); plain.set_own_order(OWN)
    _feed(plain)
    assert [n for _, n in plain.plays[1]][-1] == 'Goblins' and plain.stats['cycle_conflict_dropped:1'] == 1
    rs = ResyncTranslator(rt, OWN, plays_from='events'); rs.set_own_order(OWN)
    _feed(rs)
    names = [n for _, n in rs.plays[1]]
    assert names[-1] == 'MiniPekka' and rs.stats['resync'] == 1 and rs.resynced
    inj = [r for r in rs.public_events if r.get('injected')]
    assert inj and all(r['name'] in DECK8[:4] and 380 < r['tick'] < 500 for r in inj)
    # the corrected history is consistent for a fresh frozen tracker (what a restarted player rebuilds)
    from imitation.evaluation.d1 import PublicEvent as D1Event
    from derived_d1 import DerivedD1
    d = DerivedD1(rt.R.costs)
    for r in sorted((r for r in rs.public_events if r['seat'] == 1), key=lambda r: r['tick']):
        d.accept(D1Event(r['tick'], 'card', r['name'], 0., r['x'], r['y']))
    assert [e.name for e in rs.events] == names
    # the mirror holds the resynced play too: a duplicate detection of it right after is rejected, not accepted
    from test_live import record
    rs.information(record(tick=540, units=[], events=[dict(owner=1, card='MiniPekka', x=9., y=24., tick=540, tick_unit='tick')]))
    assert [n for _, n in rs.plays[1]].count('MiniPekka') == 2 and rs.stats['resync_skip_duplicate'] == 1


def test_resync_skips_duplicate_detections(rt):
    """The same card again within dup_ticks is a duplicate detection (real repeats need four plays first): dropped."""
    from bot.live.resync import ResyncTranslator
    from test_live import OWN, record
    rs2 = ResyncTranslator(rt, OWN, plays_from='events'); rs2.set_own_order(OWN)
    for t in range(95, 200, 5):
        ev = [dict(owner=1, card='Knight', x=9., y=24., tick=pt, tick_unit='tick') for pt in (100, 140) if t - 5 < pt <= t]
        rs2.information(record(tick=t, units=[], events=ev))
    assert rs2.stats['resync_skip_duplicate'] == 1 and [n for _, n in rs2.plays[1]] == ['Knight']


def test_resync_is_fair_information_invariant(rt):
    """Opponent-private keys in the records (its deck, hand, elixir) change nothing, resync included."""
    from bot.live.resync import ResyncTranslator
    from test_live import OWN
    a = ResyncTranslator(rt, OWN, plays_from='events'); a.set_own_order(OWN); _feed(a)
    b = ResyncTranslator(rt, OWN, plays_from='events'); b.set_own_order(OWN)
    _feed(b, extra=dict(opponent_deck=list(reversed(DECK8)), opponent_hand=['Goblins'] * 4, opponent_elixir=0.,
                        opp_cycle=['Knight', 'Archers'], hidden_plays=MISSED))
    assert a.public_events == b.public_events and a.events == b.events and dict(a.stats) == dict(b.stats)


def test_restarted_player_rebuilds_from_the_corrected_history(rt):
    from bot.live.player import LivePlayer
    from bot.live.resync import ResyncTranslator, restart_if_resynced
    from bot.players.base import MatchContext, PublicView
    from test_live import OWN, record
    rs = ResyncTranslator(rt, OWN, plays_from='events'); rs.set_own_order(OWN)
    ctx = MatchContext(seat=0, seed=3, own_order=tuple(OWN))
    for tier in ('fast', 'search'):
        p = LivePlayer(rt, tier=tier, wall_ms=None if tier == 'search' else 200, threads=1)
        p.start(ctx)
        rs = ResyncTranslator(rt, OWN, plays_from='events'); rs.set_own_order(OWN)
        plays, restarted, errs = SEEN + [CONFLICT], 0, []
        for t in range(95, 560, 5):
            ev = [dict(owner=1, card=c, x=9., y=24., tick=pt, tick_unit='tick') for pt, c in plays if t - 5 < pt <= t]
            info = rs.information(record(tick=t, units=[], events=ev, elixir=7.))
            restarted += restart_if_resynced(rs, p, ctx)
            d = p.act(PublicView(t, 0, info, info, rs.public_events, (), True))
            if d.stats and d.stats.get('error'):
                errs.append(d.stats['error'])
        assert restarted == 1 and not errs, (tier, errs[:2])
        p.close()
