"""Open-world belief regressions (cards/belief-robust) on the actual frozen + s1 resumable belief sources (no runtime):
    python -m pytest -q bot/fullpool/test_belief_robust.py"""
import copy
import importlib.util
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
    monkeypatch.setenv('BOT_BELIEF_REBUILD_SHARE', '0.01')
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
