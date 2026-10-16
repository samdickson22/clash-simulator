"""Evidence-ranked revealed set (bot/noise/livefix = the proposed bot/live patch; bot lead noise worker).

    PYTHONPATH=. CLASHER_BOT_RUNTIME=... nice -n 19 python -m pytest -q bot/noise/test_revealed.py

Proposed as bot/live/test_revealed.py with `bot.noise.livefix.` -> `bot.live.`.
"""
import numpy as np
import pytest

from bot.noise.livefix.revealed import RevealedSet

OWN = ['Knight', 'Archers', 'Giant', 'Musketeer', 'MiniPekka', 'Fireball', 'Arrows', 'Goblins']
# opponent: 7 real cards, then a spurious Earthquake fills the set; its real Log is locked out
REAL = ['HogRider', 'Valkyrie', 'Zap', 'Cannon', 'SkeletonArmy', 'Musketeer', 'Fireball']


@pytest.fixture(scope='module')
def rt():
    from bot.players.runtime import Runtime
    return Runtime()


def _rec(tick, units=(), events=(), **kw):
    r = dict(tick=tick, elixir=5.0, hand=dict(cards=OWN[:4], next=OWN[4]), units=list(units), events=list(events),
             towers=[dict(owner=0, kind='princess', side='left', hp_frac=1., alive=True)])
    r.update(kw)
    return r


def _ev(card, tick, x=9.0, y=22.0):
    return dict(owner=1, card=card, x=x, y=y, tick=tick)


TROOPS = {'HogRider', 'Valkyrie', 'Cannon', 'SkeletonArmy', 'Musketeer'}


def _locked_out_stream(log_plays=(2600, 3400), board=None, lag=0):
    """Records every 5 ticks: REAL[:4], the spurious Earthquake, REAL[4:], Zap and HogRider again, then Log (the real
    8th card). Each real troop play is on the board for 5 s (perceived). `lag`: a play event first appears in a record
    up to `lag` ticks after its own tick (a lagged detection: event tick < record tick)."""
    order = REAL[:4] + ['Earthquake'] + REAL[4:]
    plays = {200 + 200*i: c for i, c in enumerate(order)}
    plays.update({2000: 'Zap', 2200: 'HogRider'})
    plays.update({t: 'Log' for t in log_plays})
    for tick in range(100, 3600, 5):
        ev = [_ev(plays[t], t) for t in plays if tick - 5 < t + lag <= tick]
        units = [dict(card=c, owner=1, x=9.0, y=20.0, hp_frac=1., score=.8) for t, c in plays.items()
                 if c in TROOPS and t <= tick < t + 100]
        units += board(tick) if board else []
        yield _rec(tick, units=units, events=ev)


def _run(rt, cls_name='resync', evict=True, stream=None, **rkw):
    from bot.noise.livefix.resync import ResyncTranslator
    from bot.noise.livefix.translate import LiveTranslator
    cls = ResyncTranslator if cls_name == 'resync' else LiveTranslator
    tr = cls(rt, OWN, plays_from='events')
    tr.revealed.evict = evict
    restarts, info = 0, None
    for r in stream if stream is not None else _locked_out_stream(**rkw):
        info = tr.information(r)
        if getattr(tr, 'resynced', False):
            tr.resynced, restarts = False, restarts + 1
    return tr, info, restarts


def test_off_is_the_first_come_rule():
    rows = []
    s = RevealedSet(rows)          # plays=None: members from the rows
    for i, c in enumerate(REAL + ['Earthquake']):
        rows.append(dict(seat=1, tick=100*i, kind='card', name=c))
    assert s.allows('Earthquake') and not s.allows('Log') and s.victim('Log', 5000) is None
    s.reject('Log', 4000, 9, 20)
    s.reject('Log', 4500, 9, 20)
    assert s.victim('Log', 4600) is None            # evict off: never


def test_lockout_without_eviction(rt):
    tr, info, restarts = _run(rt, evict=False)
    assert 'Log' not in tr.revealed.members() and 'Earthquake' in tr.revealed.members()
    assert tr.stats['ninth_enemy_card_dropped'] == 2 and restarts == 0


def test_repeated_plays_evict_the_weak_card_and_resync(rt):
    """Two Log plays (2600, 3400) evict the once-seen Earthquake; the history, mirror and stream are rewritten."""
    from derived_d1 import DerivedD1
    tr, info, restarts = _run(rt)
    m = tr.revealed.members()
    assert 'Log' in m and 'Earthquake' not in m and len(m) == 8
    assert tr.stats['evict:Earthquake->Log'] == 1 and restarts >= 1
    opp = [r for r in tr.public_events if r['seat'] == 1]
    assert [n for _, n in tr.plays[1]] == [r['name'] for r in opp] == [e.name for e in tr.events]
    assert [r['name'] for r in opp].count('Log') == 2 and 'Earthquake' not in {r['name'] for r in opp}
    # cycle tracker re-synced: a fresh replay of the public history gives the translator's mirror
    import copy
    fresh, mirror = tr._replay(tr._history(), tr.tick), copy.deepcopy(tr._mirrors[1])
    mirror.advance(tr.tick)
    assert list(fresh.queue) == list(mirror.queue) and fresh.revealed == mirror.revealed
    assert {e.name for e in info.events} == set(m)
    # the evicted card's play is evidence again: it comes back only on new evidence
    assert tr.revealed.plays('Earthquake') == 1


def test_lagged_play_eviction_keeps_time_monotone(rt):
    """A play-triggered eviction from a lagged event (event tick 5 ticks before its record's tick): the rebuilt mirror
    must not run ahead of that event, or the event's own stream-guard check raises 'public time moved backwards'."""
    tr, info, restarts = _run(rt, lag=3)
    m = tr.revealed.members()
    assert 'Log' in m and 'Earthquake' not in m and tr.stats['evict:Earthquake->Log'] == 1 and restarts >= 1
    assert [n for _, n in tr.plays[1]].count('Log') == 2      # the evicting play itself is accepted


def test_board_eviction_then_lagged_event_in_the_same_record(rt):
    """A board-triggered eviction (assign runs before accept_events) followed, in the same record, by an opponent
    play event earlier than the record tick: the event is processed normally (no time-backwards error)."""
    from bot.noise.livefix.resync import ResyncTranslator
    tr = ResyncTranslator(rt, OWN, plays_from='events')
    t_evict = None
    for r in _locked_out_stream(log_plays=(), board=_giant_board()):
        tr.information(r)
        if tr.stats['evict'] and t_evict is None:
            t_evict = r['tick']
    assert t_evict is not None

    def stream():
        for r in _locked_out_stream(log_plays=(), board=_giant_board()):
            if r['tick'] == t_evict:
                r = dict(r, events=r['events'] + [_ev('Valkyrie', t_evict - 3)])
            yield r
    tr2, _, restarts = _run(rt, stream=stream())
    assert tr2.stats['evict:Earthquake->Giant'] == 1 and 'Giant' in tr2.revealed.members() and restarts >= 1
    assert (t_evict - 3, 'Valkyrie') in tr2.plays[1] or tr2.stats['cycle_conflict_dropped:1'] >= 1


def test_one_play_is_not_enough(rt):
    tr, _, restarts = _run(rt, log_plays=(2600,))
    assert 'Log' not in tr.revealed.members() and restarts == 0 and tr.stats['evict'] == 0


def test_well_evidenced_cards_are_never_evicted(rt):
    """Every member played twice, troops seen on the board (none weak): a 9th card cannot get in however often."""
    order = REAL + ['Earthquake']
    plays = {200 + 150*i: c for i, c in enumerate(order + order)}
    plays.update({t: 'Log' for t in (3000, 3200, 3400)})

    def units(tick):
        return [dict(card=c, owner=1, x=9.0, y=20.0, hp_frac=1., score=.8) for t, c in plays.items()
                if c in TROOPS and t <= tick < t + 100]
    stream = (_rec(t, units=units(t), events=[_ev(plays[p], p) for p in plays if t - 5 < p <= t])
              for t in range(100, 3600, 5))
    tr, _, _ = _run(rt, stream=stream)
    assert 'Log' not in tr.revealed.members() and tr.stats['evict'] == 0 and tr.stats['evict_refused'] >= 1


def _giant_board(t0=2500, frames=tuple(range(30))):
    def board(tick):
        k = (tick - t0)//5
        if k in frames:
            return [dict(card='Giant', owner=1, x=9.5, y=22.0 - .05*k, hp_frac=1., score=.8)]
        return []
    return board


def test_board_and_sanitizer_share_the_set(rt):
    """A persistent unit of an unseen card (Giant, its play never perceived; 10 records meeting 3-of-4) displaces
    the weakest card W (the once-seen Earthquake), and from then on the sanitizer keeps Giant units and drops W's (one set for plays and board)."""
    tr, info, restarts = _run(rt, log_plays=(), board=_giant_board())
    assert tr.stats['evict'] == 1 and 'Giant' in tr.revealed.members() and restarts == 1
    assert tr.stats['evict:Earthquake->Giant'] == 1
    dropped = tr.stats['board_dropped:1:Giant']       # the frames before the k-of-n rule admitted it
    assert 0 < dropped <= 12
    assert tr.board_card_ok('Giant', 1) and not tr.board_card_ok('Earthquake', 1)
    assert not tr.revealed.allows('Earthquake')        # and its plays are rejected too


def test_flicker_is_not_board_evidence(rt):
    """False positives / per-frame confusion: a card seen on isolated frames never meets the k-of-n rule."""
    tr, _, _ = _run(rt, log_plays=(), board=_giant_board(frames=tuple(range(0, 200, 3))))
    assert tr.stats['evict'] == 0 and 'Giant' not in tr.revealed.members()
    assert tr.stats['board_dropped:1:Giant'] > 0


def test_contradicted_troop_goes_first(rt):
    """Two weak members (each played once, no board record): the troop card the board never confirmed (HogRider
    here, deployed but never seen) is evicted before the spell (Zap), whatever their age."""
    order = ['Zap', 'HogRider', 'Valkyrie', 'Cannon', 'SkeletonArmy', 'Musketeer', 'Fireball', 'Earthquake']
    plays = {200 + 200*i: c for i, c in enumerate(order)}
    plays.update({t: 'Log' for t in (2600, 3400)})
    seen = {'Valkyrie': 600, 'Cannon': 800, 'SkeletonArmy': 1000, 'Musketeer': 1200}

    def units(tick):
        return [dict(card=c, owner=1, x=9.0, y=20.0, hp_frac=1., score=.8) for c, t in seen.items() if t <= tick < t + 100]
    stream = (_rec(t, units=units(t), events=[_ev(plays[p], p) for p in plays if t - 5 < p <= t])
              for t in range(100, 3600, 5))
    tr, _, _ = _run(rt, stream=stream)
    assert tr.stats['evict:HogRider->Log'] == 1, dict(tr.stats)


def test_fair_information_invariance(rt):
    """The decision input (packet, enemy events, public rows, revealed set, eviction counters) is a function of the
    perception records only: opponent-private truth added to the records (deck, hand, elixir, true card ids of
    units, the true revealed set) changes nothing."""
    def poisoned():
        for r in _locked_out_stream(board=_giant_board()):
            r = dict(r, opponent=dict(deck=REAL + ['Log'], hand=['Log']*4, elixir=9.9, revealed=REAL + ['Log']),
                     opp_elixir=0.1, opp_hand=['Zap']*4)
            r['units'] = [dict(u, private_card_id=26000000, true_card='Log') for u in r['units']]
            r['events'] = [dict(e, true_card='Log') for e in r['events']]
            yield r
    a, ia, ra = _run(rt, stream=_locked_out_stream(board=_giant_board()))
    b, ib, rb = _run(rt, stream=poisoned())
    assert a.stats['evict'] >= 1
    assert dict(a.stats) == dict(b.stats) and ra == rb and a.revealed.members() == b.revealed.members()
    assert a.public_events == b.public_events and ia.events == ib.events and ia.own == ib.own
    for f in ('entity_ids', 'entity_features', 'hand_ids', 'global_features', 'opponent_history_ids',
              'opponent_seen_card_ids'):
        assert np.array_equal(getattr(ia.packet.observation, f), getattr(ib.packet.observation, f)), f


# -- review r5: board-only admissions reach the belief; same-frame refilter; real-frame evidence -------------------
class _Probe:
    """Stub player: a fresh live belief per start() (as LivePlayer's search tier), updated from each view's enemy
    events; never acts."""
    name, deadline_seconds = 'probe', None

    def __init__(self, rt, belief=True):
        self.rt, self.belief_on, self.starts = rt, belief, 0

    def start(self, ctx):
        self.starts += 1
        if self.belief_on:
            from fair_player import PublicPlanner
            from bot.live.player import live_belief_class
            self.belief = PublicPlanner(self.rt.R, self.rt.PRIOR, 1).belief
            self.belief.__class__ = live_belief_class()
            self.belief.human_prior = self.rt.PRIOR

    def act(self, view):
        from bot.players.base import Decision, WAIT
        if self.belief_on:
            self.belief.update(view.info.tick, view.info.events)
        self.info = view.info
        return Decision(WAIT, stats={})

    def close(self):
        pass


def _session(rt, player, stream):
    from bot.noise.livefix.resync import ResyncTranslator
    from bot.noise.livefix.translate import LiveSession
    s = LiveSession(rt, player, OWN, seed=7, translator=ResyncTranslator(rt, OWN, plays_from='events'))
    for r in stream:
        s.step(r)
    return s


def test_board_admission_reaches_the_belief_after_restart(rt):
    """Giant is admitted on board evidence alone (its play never perceived) and evicts Earthquake. It must enter the
    public deck constraints: an inferred play row (injected, board) in the history, the mirror, the enemy event stream
    and so every opponent deck the restarted player's belief samples (8 known cards: the deck is determined)."""
    probe = _Probe(rt)
    s = _session(rt, probe, _locked_out_stream(log_plays=(), board=_giant_board()))
    tr = s.tr
    assert tr.stats['evict:Earthquake->Giant'] == 1 and probe.starts >= 2 and tr.restarts >= 1
    want = set(REAL) | {'Giant'}
    for seed in range(16):
        d = probe.belief.sample(np.random.default_rng(seed))
        assert set(c for c in d['hand'] + d['cycle'] if c) == want, (seed, d)
    assert 'Giant' in tr._mirrors[1].revealed and 'Earthquake' not in tr._mirrors[1].revealed
    assert 'Giant' in {e.name for e in probe.info.events} and tr.revealed.plays('Giant') == 0   # not play evidence
    rows = [r for r in tr.public_events if r['seat'] == 1 and r['name'] == 'Giant']
    assert len(rows) == 1 and rows[0]['injected'] and rows[0]['board'] and rows[0]['tick'] <= 2500
    assert tr.revealed.board_plays['Giant'][0] == rows[0]['tick']


def test_board_play_survives_a_later_eviction(rt):
    """A later play-triggered eviction rebuilds the history from perceived plays: the board-admitted card's inferred
    play is re-inserted (it is not perception evidence, but it is a member)."""
    tr, info, restarts = _run(rt, log_plays=(3000, 3400), board=_giant_board())
    assert tr.stats['evict:Earthquake->Giant'] == 1 and tr.stats['evict'] == 2 and 'Log' in tr.revealed.members()
    opp = {r['name'] for r in tr.public_events if r['seat'] == 1}
    assert 'Giant' in opp and 'Log' in opp and len(opp) == 8 and opp == tr._mirrors[1].revealed
    assert {e.name for e in info.events} == opp == tr.revealed.members()


def _opp_bodies(info, rt):
    o = info.packet.observation
    names = rt.R.builder.token_names
    return [names[int(o.entity_ids[i])] for i in np.flatnonzero(o.entity_mask) if o.entity_features[i][2] < .5]


def test_same_frame_eviction_refilters_the_board(rt):
    """A play evicts HogRider (contradicted: played once, never confirmed on board) for Giant in a frame that holds
    units of BOTH cards. The sanitizer ran before the eviction; the frame's packet must still match the final set:
    the Giant unit is kept and the HogRider unit dropped, each counted once."""
    order = ['Zap', 'HogRider', 'Valkyrie', 'Cannon', 'SkeletonArmy', 'Musketeer', 'Fireball', 'Earthquake']
    plays = {200 + 200*i: c for i, c in enumerate(order)}
    plays[2600] = 'Giant'
    both = [dict(card='HogRider', owner=1, x=4.0, y=18.0, hp_frac=1., score=.8),
            dict(card='Giant', owner=1, x=9.5, y=22.0, hp_frac=1., score=.8)]
    from bot.noise.livefix.resync import ResyncTranslator
    tr = ResyncTranslator(rt, OWN, plays_from='events')
    tr.set_own_order(OWN)
    for t in range(100, 2605, 5):
        info = tr.information(_rec(t, units=both if t == 2600 else (),
                                   events=[_ev(plays[p], p) for p in plays if t - 5 < p <= t]))
    assert tr.stats['evict:HogRider->Giant'] == 1, dict(tr.stats)
    bodies = _opp_bodies(info, rt)
    assert any('Giant' in b for b in bodies) and not any('Hog' in b for b in bodies), bodies
    s = tr.stats
    assert s['board_refilter_kept'] == 1 and s['board_refilter_dropped'] == 1
    assert s['board_dropped:1:Giant'] == 0 and s['board_dropped:1:HogRider'] == 1 and s['board_dropped'] == 1
    assert tr.board_card_ok('Giant', 1) and not tr.board_card_ok('HogRider', 1)


def test_catch_up_polls_are_not_board_evidence(rt):
    """A frame gap (2400 -> 2465): LiveSession repeats the one snapshot over 12 catch-up polls. A single Giant
    sighting is ONE evidence record, so it neither meets persistence nor evicts."""
    def stream():
        for r in _locked_out_stream(log_plays=()):
            if 2400 < r['tick'] < 2465:
                continue
            if r['tick'] == 2465:
                r = dict(r, units=r['units'] + _giant_board(2465, (0,))(2465))
            yield r
    s = _session(rt, _Probe(rt, belief=False), stream())
    tr = s.tr
    assert tr.stats['evict'] == 0 and 'Giant' not in tr.revealed.members()
    assert tr.revealed.seen['Giant'] == [2465] and tr.revealed.board['Giant'] == 0
    assert tr.stats['catchup_polls'] == 12 and tr.stats['board_evidence_skipped'] == 12


def test_catch_up_after_a_gap_keeps_real_persistence(rt):
    """Persistent real sightings around a gap still count, once per real frame: Giant on 30 real frames with a gap
    in the middle gets exactly one board record per real frame meeting 3-of-4, like the same frames without the
    catch-up polls."""
    def stream(gap):
        for r in _locked_out_stream(log_plays=(), board=_giant_board()):
            if gap and 2550 < r['tick'] < 2600:
                continue
            yield r
    a = _session(rt, _Probe(rt, belief=False), stream(True)).tr
    b = _run_tr(rt, stream(True))
    assert a.stats['catchup_polls'] == 9 and a.revealed.board == b.revealed.board
    assert a.revealed.seen == b.revealed.seen and a.stats['evict'] == b.stats['evict'] == 1


def _run_tr(rt, stream):
    tr, _, _ = _run(rt, stream=stream)
    return tr


def test_repeated_frames_are_idempotent(rt):
    """Feeding every record twice (same frame identity) gives the same RevealedSet evidence, eviction and public
    history as feeding it once."""
    def twice():
        for r in _locked_out_stream(board=_giant_board()):
            yield r
            yield dict(r)
    a, ia, ra = _run(rt, stream=_locked_out_stream(board=_giant_board()))
    b, ib, rb = _run(rt, stream=twice())
    assert a.stats['evict'] >= 1
    assert a.revealed.board == b.revealed.board and a.revealed.seen == b.revealed.seen
    assert a.revealed.members() == b.revealed.members() and a.revealed.admitted == b.revealed.admitted
    assert {k: v for k, v in a.stats.items() if k.startswith('evict')} == \
        {k: v for k, v in b.stats.items() if k.startswith('evict')}
    assert a.public_events == b.public_events and ia.events == ib.events and ra == rb
    assert b.stats['board_evidence_skipped'] == 700
