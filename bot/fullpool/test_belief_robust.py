"""Open-world belief regressions (cards/belief-robust) on the actual frozen + s1 resumable belief sources (no runtime):
    python -m pytest -q bot/fullpool/test_belief_robust.py"""
import copy
import importlib.util
import time
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from bot.fullpool import banks, belief
from bot.fullpool.cards import POOL
from bot.fullpool.decks import Sampler

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def base(monkeypatch):
    # Load the same two implementations as Runtime, without a native library/checkpoints.
    path = REPO / 'reports/strategy_council_20260928/engine-speed/stage5/derived_public_state.py'
    spec = importlib.util.spec_from_file_location('derived_public_state', path)
    frozen = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, 'derived_public_state', frozen)
    spec.loader.exec_module(frozen)
    spec = importlib.util.spec_from_file_location('robust_s1', REPO / 'reports/explore/s1/belief.py')
    s1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s1)
    return s1.Belief, frozen.PublicEvent


def make(base, n=16):
    cls, event = base
    sampler = Sampler.from_spec('fullpool-uniform:52')
    prior = belief.prior_decks(sampler, n)
    costs = dict.fromkeys(POOL, 3.)
    b = belief.fullpool_belief_class(cls, sampler, n)(prior, costs)
    return b, event


def equal(a, b):
    for key in ('states', 'weights', 'cumulative'):
        np.testing.assert_array_equal(getattr(a, key), getattr(b, key))
    for key in ('tick', 'refill', 'queue_len', 'elixir', 'events', 'names', 'ids'):
        assert getattr(a, key) == getattr(b, key)
    assert a.derived() == b.derived()
    ra, rb = np.random.default_rng(7), np.random.default_rng(7)
    assert [a.sample(ra) for _ in range(20)] == [b.sample(rb) for _ in range(20)]
    assert ra.bit_generator.state == rb.bit_generator.state


def represented(b, names):
    assert len(b.states)
    for c in names:
        assert np.all(np.any(b.states == b.ids[c], axis=1)), c
    rows = b.states[:, :4 + b.queue_len]
    assert np.all(np.count_nonzero(rows, axis=1) == 8)
    for row in rows[::max(1, len(rows)//30)]:
        assert len(set(row[row != 0])) == 8


def test_late_reveal_after_several_rebuilds(base):
    b, event = make(base, n=1)
    events, seen = [], []
    for tick in (100, 200, 300, 1000, 1100):
        # Pick a card absent from every current deck, forcing a new rebuild each time.
        present = {b.names[int(i)-1] for i in np.unique(b.states) if i}
        name = next(c for c in POOL if c not in present and c not in seen and c not in ('ArcherQueen', 'BossBandit'))
        seen.append(name)
        events.append(event(tick, 'card', name))
        b.update(tick, events)
        assert b.rebuilds == len(events)
        represented(b, seen)
        b.update(tick + 25, events)
        represented(b, seen)


def test_unknown_alias_and_valid_engine_sample(base):
    b, event = make(base)
    events = [event(100, 'card', 'Evolution Knight'), event(200, 'card', 'Future Mystery Card'),
              event(300, 'card', 'Rune Giant'), event(400, 'card', 'Archers'), event(500, 'card', 'Arrows'),
              event(600, 'card', 'Zap'), event(700, 'card', 'Bats'),
              event(1000, 'card', 'Future Mystery Card')]   # back in hand after a full cycle
    for i, e in enumerate(events):
        b.update(e.tick, events[:i+1])
    represented(b, ['Knight', '~futuremysterycard', 'GiantBuffer'])
    assert 1 <= b.costs['~futuremysterycard'] <= 10
    for _ in range(30):
        s = b.sample(np.random.default_rng(_))
        deck = [c for c in s['hand'] + s['cycle'] if c]
        assert len(deck) == len(set(deck)) == 8 and set(deck) <= set(POOL)
    assert events[0].name == 'Evolution Knight'  # never mutate caller's public stream


def test_explicit_c56_beats_environment(monkeypatch):
    monkeypatch.setenv('BOT_BELIEF_PRIOR', 'fullpool:7')
    monkeypatch.delenv('BOT_CYCLE_MODEL', raising=False)
    rt = SimpleNamespace(PRIOR=object())
    banks.select(rt, 'e16bl', 'c56')
    assert rt.belief_prior == belief.belief_spec(rt) == 'c56'
    cls = type('Base', (), {})
    prior, selected = belief.planner_belief(rt, cls)
    assert prior is rt.PRIOR and selected is cls


def test_rebuild_suspends_resumes_and_includes_new_late_event(base, monkeypatch):
    a, event = make(base)
    b, _ = make(base)
    events = [event(100, 'card', 'Future Mystery Card')]
    before = copy.deepcopy(b.__dict__)
    # Incrementing fake clock: each call receives a strict, deterministic work budget.
    now = [0.]
    def clock():
        now[0] += .00001
        return now[0]
    monkeypatch.setenv('BOT_BELIEF_REBUILD_SHARE', '0.001')   # ~10 clock calls of work per decision
    monkeypatch.setattr(belief, 'REBUILD_MIN', 0.)               # no floor on the fake clock
    b.update(100, events, deadline=now[0] + .1, clock=clock)
    assert b.stale and b._job is not None
    np.testing.assert_array_equal(b.states, before['states'])
    assert b.tick == 0 and not b.events
    b.sample(np.random.default_rng(1))  # stale posterior remains usable
    a.update(100, events)               # the synchronous twin sees the same update sequence
    events.append(event(200, 'card', 'Rune Giant'))
    a.update(200, events)
    for tries in range(2000):
        b.update(200, events, deadline=now[0] + .1, clock=clock)
        if not b.stale:
            break
    else:
        pytest.fail('rebuild did not complete')
    assert tries > 0 and b.rebuild_slices > 1 and b._job is None
    equal(a, b)
    represented(b, ['~futuremysterycard', 'GiantBuffer'])


def test_expired_deadline_does_no_rebuild_work(base, monkeypatch):
    b, event = make(base)
    def forbidden(*args, **kwargs):
        pytest.fail('rebuild ran after deadline')
    monkeypatch.setattr(belief, 'prior_work', forbidden)
    b.update(100, [event(100, 'card', 'Future Mystery Card')], deadline=0., clock=lambda: 0.)
    assert b.stale and b._job is not None and b.tick == 0


def test_chunked_init_exactly_matches_frozen(base):
    cls, _ = base
    s = Sampler.from_spec('fullpool-uniform:4')
    prior = belief.prior_decks(s, 16)
    costs = dict.fromkeys(POOL, 3.)
    a, b = cls(prior, costs), cls(prior, costs)
    belief._run(belief.init_work(b, prior, costs, block=1))
    equal(a, b)


def test_known_stream_passes_through_unchanged(base):
    b, event = make(base)
    events = [event(100, 'card', 'Knight'), event(150, 'ability', amount=1.), event(200, 'card', 'Archers')]
    assert b.canonical(events) is events


def test_impossible_reveals_are_dropped_not_fatal(base):
    b, event = make(base)
    names = [c for c in POOL if c not in ('ArcherQueen', 'BossBandit', 'Goblinstein', 'GoldenKnight', 'LittlePrince',
                                          'MightyMiner', 'Monk', 'SkeletonKing')][:9]
    events = [event(100 + 50*i, 'card', c) for i, c in enumerate(names)]
    events += [event(600, 'card', 'ArcherQueen'), event(650, 'card', 'BossBandit')]
    b.update(700, events)          # a 9th distinct card and a 2nd champion cannot be in one deck: dropped
    assert b.dropped == 3 and len(b.events) == len(events) - 3
    represented(b, names[:8])


def test_unknown_under_deadline_equals_synchronous(base, monkeypatch):
    a, event = make(base)
    b, _ = make(base)
    events = [event(100, 'card', 'Knight'), event(300, 'card', 'Future Mystery Card'), event(500, 'card', 'Archers Evo')]
    now = [0.]

    def clock():
        now[0] += .00001
        return now[0]
    monkeypatch.setenv('BOT_BELIEF_REBUILD_SHARE', '0.001')
    belief._PRIORS.clear()
    monkeypatch.setattr(belief, 'REBUILD_MIN', 0.)               # no floor on the fake clock
    for i, e in enumerate(events):
        a.update(e.tick + 10, events[:i + 1])
        for _ in range(5000):
            b.update(e.tick + 10, events[:i + 1], deadline=now[0] + .1, clock=clock)
            if not b.stale:
                break
        equal(a, b)
    assert a.rebuilds == b.rebuilds >= 1 and b.rebuild_slices >= 1


def test_live_belief_layer(base):
    cls, event = base
    sampler = Sampler.from_spec('fullpool-uniform:9')
    catalog = belief.prior_decks(sampler, 20)
    costs = dict.fromkeys(POOL, 3.)
    from bot.live import player
    LB = belief.open_world_class(cls, 'LiveBelief', lambda self, r: (yield) or player.completed_prior(catalog, r),
                                 lambda self: {c: 1. for c in POOL})
    b = LB(catalog, costs)
    assert type(b).__mro__[1] is cls      # fp_mac_bench FP_TEST_BELIEF_REBUILD patches __mro__[1].update
    events = [event(100, 'card', 'Future Mystery Card'), event(200, 'card', 'Mini P.E.K.K.A')]
    b.update(300, events)
    represented(b, ['~futuremysterycard', 'MiniPekka'])
    s = b.sample(np.random.default_rng(3))
    assert not any(c and c.startswith('~') for c in s['hand'] + s['cycle'])


def test_second_champion_is_dropped_before_eight_cards(base):
    b, event = make(base)
    # hero / evolution spellings that resolve to champions; the 2nd and 3rd champions arrive with 2 and 3 cards revealed
    events = [event(100, 'card', 'Knight'), event(200, 'card', 'Evo Archer Queen'), event(300, 'card', 'Archers'),
              event(400, 'card', 'Hero Golden Knight'), event(500, 'card', 'Monk'), event(600, 'card', 'Arrows')]
    b.update(700, events)
    assert b.dropped == 2 and [e.name for e in b.events] == ['Knight', 'ArcherQueen', 'Archers', 'Arrows']
    represented(b, ['Knight', 'ArcherQueen', 'Archers', 'Arrows'])
    assert not np.any(b.states == b.ids['GoldenKnight']) and not np.any(b.states == b.ids['Monk'])


@pytest.mark.parametrize('raw', ['bad', 'nan', 'inf', '-1', '0', '5', ''])
def test_rebuild_share_validated(base, monkeypatch, raw):
    monkeypatch.setenv('BOT_BELIEF_REBUILD_SHARE', raw)
    assert belief.rebuild_share() == belief.REBUILD_SHARE
    b, event = make(base)
    b.update(100, [event(100, 'card', 'Future Mystery Card')], deadline=time.monotonic() + 5., clock=time.monotonic)
    assert b.rebuilds == 1 and not b.stale
    monkeypatch.setenv('BOT_BELIEF_REBUILD_SHARE', '0.25')
    assert belief.rebuild_share() == 0.25


def _fake_clock():
    now = [0.]

    def clock():
        now[0] += 1e-5
        return now[0]
    return now, clock


def test_one_rebuild_cutoff_per_update(base, monkeypatch):
    """A rebuild that finishes and a second one the newer history needs share ONE cutoff within an update()."""
    monkeypatch.setattr(belief, 'REBUILD_MIN', 0.)
    event = base[1]
    e1 = [event(100, 'card', 'Future Mystery Card')]
    e2 = e1 + [event(200, 'card', 'Second Mystery Card')]
    belief._PRIORS.clear()
    probe, _ = make(base)
    now, clock = _fake_clock()
    t0 = now[0]
    probe.update(100, e1, deadline=t0 + 1e6, clock=clock)
    calls = (now[0] - t0) / 1e-5                     # job length in clock calls (one per work step)
    assert probe.rebuilds == 1 and calls > 50
    belief._PRIORS.clear()
    b, _ = make(base)
    monkeypatch.setenv('BOT_BELIEF_REBUILD_SHARE', str(0.6 * calls * 1e-5))   # slice = 0.6 job, of a 1 s budget
    b.update(100, e1, deadline=now[0] + 1., clock=clock)
    assert b.stale and b._job is not None
    t1 = now[0]
    b.update(200, e2, deadline=t1 + 1., clock=clock)
    used = (now[0] - t1) / 1e-5
    assert b.rebuilds == 1 and b.stale and b._job is not None      # job 1 installed, job 2 started, then stopped
    assert used <= 0.6 * calls + 10, (used, calls)               # not a fresh share for job 2 (old: ~1.0 job)


def test_rebuild_overshoot_bounded(base):
    """400-deck prior (672,000 states, as live), real clock, 0.5 ms left at every call: each call returns within a
    small bound past its deadline, and the finished rebuild equals the synchronous one."""
    a, event = make(base, n=400)
    b, _ = make(base, n=400)
    events = [event(100, 'card', 'Knight'), event(150, 'ability', amount=1.), event(300, 'card', 'Future Mystery Card'),
              event(700, 'card', 'Archers')]
    a.update(900, events)
    belief._PRIORS.clear()
    over, calls = [], 0
    while True:
        calls += 1
        deadline = time.perf_counter() + .0005
        b.update(900, events, deadline=deadline, clock=time.perf_counter)
        over.append(time.perf_counter() - deadline)
        if not b.stale:
            break
        assert calls < 20000
    over.sort()
    print(f'overshoot: calls {calls}, p50 {1e3 * over[len(over) // 2]:.3f} ms, max {1e3 * over[-1]:.3f} ms')
    assert calls > 20 and over[-1] < .001, (calls, over[-5:])
    equal(a, b)


def test_cumsum_work_is_bit_identical_on_float_weights():
    w = np.random.default_rng(5).random(3 * 4096 * 4 + 17) * 0.37     # catalog-like non-integer frequencies
    np.testing.assert_array_equal(belief._run(belief.cumsum_work(w, rows=4096)), np.cumsum(w))
    out = np.empty(len(w) + 9)
    got = belief._run(belief.cumsum_work(w, rows=1000, out=out[:len(w)]))
    assert got.base is out and np.array_equal(got, np.cumsum(w))
