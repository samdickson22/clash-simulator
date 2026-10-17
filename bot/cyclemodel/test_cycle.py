"""Cycle model tests against the frozen belief (stage5 derived_public_state + s1 belief from the runtime root).

    PYTHONHASHSEED=0 .venv/bin/python -m pytest -q bot/cyclemodel/test_cycle.py
"""
from __future__ import annotations

import itertools
import os
import random
import sys
from pathlib import Path

import numpy as np
import pytest

from bot.cyclemodel.belief import NO_DECK, cycle_belief_class, parse_spec

ROOT = Path(os.environ.get('CLASHER_BOT_RUNTIME', '/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1'))
for sub in ('reports/explore/s1', 'reports/strategy_council_20260928/engine-speed/stage5'):
    if str(ROOT / sub) not in sys.path:
        sys.path.insert(0, str(ROOT / sub))
from derived_public_state import DerivedPublicState, PublicEvent  # noqa: E402
from belief import Belief  # noqa: E402

COSTS = dict(Knight=3, Archers=3, Fireball=4, Zap=2, Giant=5, Musketeer=4, Skeletons=1, Valkyrie=4, Arrows=3,
             HogRider=4, Goblins=2, Minions=3, Tombstone=3, Bomber=2, MiniPekka=4, Log=2)
SPELLS = {'Fireball', 'Zap', 'Arrows', 'Log'}
LAM = {n: (1.0 if n in SPELLS else 0.1) for n in COSTS}
CFG = parse_spec('soft')


def prior(seed=0, n=12):
    rng = random.Random(seed)
    names = sorted(COSTS)
    decks = {tuple(sorted(rng.sample(names, 8))) for _ in range(n)}
    return dict(decks=[dict(cards=list(d), frequency=float(1 + i % 3)) for i, d in enumerate(sorted(decks))])


def make(cls, pr):
    b = DerivedPublicState.__new__(DerivedPublicState)
    DerivedPublicState.__init__(b, pr, COSTS)
    b.__class__ = cls
    return b


class TrueOpponent:
    """The frozen belief's own dynamics on one deck/order: who plays what, when (legal by construction)."""

    def __init__(self, order):
        self.hand, self.queue = sorted(order[:4]), list(order[4:])
        self.tick, self.refill = 0, 0
        self.elixir = 6.0

    def advance(self, tick):
        while self.tick < tick:
            self.tick += 1
            rate = .93 if self.tick > 4800 else 1.4 if self.tick > 2400 else 2.8
            self.elixir = min(10., (round(self.elixir*10000)+int(500/rate))/10000) if self.elixir < 10. else self.elixir
            self.refill = max(0, self.refill-50)
            if self.refill == 0 and len(self.queue) > 4:
                self.hand.append(self.queue.pop(0))
                self.refill = 1000 if self.tick < 2400 else 500 if self.tick < 4800 else 350

    def play(self, tick, rng):
        """Pick a hand card at `tick`, wait until it is affordable; returns (tick, name)."""
        self.advance(tick)
        name = rng.choice(self.hand)
        while self.elixir < COSTS[name]:
            tick += 1
            self.advance(tick)
        self.hand.remove(name)
        self.queue.append(name)
        self.elixir = max(0., self.elixir - COSTS[name])
        return tick, name


def stream(pr, seed, n_plays=20, gap=(25, 80)):
    rng = random.Random(seed)
    deck = list(rng.choice(pr['decks'])['cards'])
    rng.shuffle(deck)
    opp, t, out = TrueOpponent(deck), 0, []
    for _ in range(n_plays):
        t, name = opp.play(t + rng.randint(*gap), rng)
        out.append((t, name))
    return deck, out


def same(a, b):
    assert np.array_equal(a.states, b.states)
    assert np.array_equal(a.weights, b.weights)
    assert (a.tick, a.refill, a.queue_len, a.elixir, a.events) == (b.tick, b.refill, b.queue_len, b.elixir, b.events)


@pytest.mark.parametrize('seed', range(25))
def test_perfect_observation_parity(seed):
    """Certain, consistent plays: rows, weights, ledger and samples equal the frozen s1 Belief, with and without a
    deadline, polled at every decision tick like the search."""
    pr = prior(seed % 5)
    cyc = cycle_belief_class(Belief, CFG, LAM)
    _, plays = stream(pr, seed)
    for deadline in (None, 1e18):
        a, b = make(Belief, pr), make(cyc, pr)
        ra, rb = np.random.default_rng(seed), np.random.default_rng(seed)
        events = []
        last = plays[-1][0] + 40
        for tick in range(10, last, 10):
            while len(events) < len(plays) and plays[len(events)][0] <= tick:
                events.append(PublicEvent(plays[len(events)][0], 'card', plays[len(events)][1]))
            kw = {} if deadline is None else dict(deadline=deadline)
            a.update(tick, list(events), **kw)
            b.update(tick, list(events), **kw)
            same(a, b)
            assert a.sample(ra) == b.sample(rb)
        assert b.cycle_stats['conflicts'] == 0


def hidden_spell_case(seed):
    """A true opponent stream where every spell play is unseen; returns (prior, deck, visible plays, all plays)."""
    pr = prior(seed % 5)
    for s in range(seed * 1000, seed * 1000 + 1000):
        deck, plays = stream(pr, s, n_plays=24)
        if not SPELLS & set(deck):
            continue
        visible = [(t, n) for t, n in plays if n not in SPELLS]
        b = make(Belief, pr)
        try:
            b.update(visible[-1][0], [PublicEvent(t, 'card', n) for t, n in visible])
        except ValueError:
            return pr, deck, visible, plays
    pytest.skip('no conflicting stream found')


@pytest.mark.parametrize('seed', range(8))
def test_unseen_spells_explained(seed):
    """Visible plays that break the frozen belief (spells unseen) are explained by hidden plays; the true deck stays
    in the posterior and every row is a legal deck permutation."""
    pr, deck, visible, _ = hidden_spell_case(seed)
    cyc = cycle_belief_class(Belief, CFG, LAM)
    b = make(cyc, pr)
    events = []
    for t, n in visible:
        events.append(PublicEvent(t, 'card', n))
        b.update(t, list(events))
    st = b.cycle_stats
    assert st['conflicts'] >= 1 and st['hidden_plays'] >= 1
    rows = {tuple(sorted(int(x) for x in r if x)) for r in b.states}
    assert tuple(sorted(b.ids[n] for n in deck)) in rows
    nz = (b.states != 0).sum(axis=1)
    assert np.all(nz == 8)
    assert all(len(set(int(x) for x in r if x)) == 8 for r in b.states[:200])


def test_soft_phantom_and_real():
    """'card?' p: mixture of real (hidden plays if needed) and phantom; p=1 'card?' equals 'card' when consistent
    up to the immediate-refill approximation; a soft card no row holds is a phantom (no raise)."""
    pr = prior(1)
    cyc = cycle_belief_class(Belief, CFG, LAM)
    deck, plays = stream(pr, 7, n_plays=6)
    events = [PublicEvent(t, 'card', n) for t, n in plays]
    b = make(cyc, pr)
    b.update(plays[-1][0], events)
    w0 = b.weights.sum()
    # phantom repeat of the last card (it is at the queue end in every row)
    t = plays[-1][0] + 5
    events.append(PublicEvent(t, 'card?', plays[-1][1], 0.3))
    b.update(t, list(events))
    assert abs(b.weights.sum() - w0) < 1e-6 * w0
    assert b.cycle_stats['soft'] == 1
    # a card no prior deck holds
    absent = next(n for n in COSTS if not any(n in d['cards'] for d in pr['decks'])) if any(
        all(n not in d['cards'] for d in pr['decks']) for n in COSTS) else None
    if absent:
        events.append(PublicEvent(t + 5, 'card?', absent, 0.9))
        b.update(t + 5, list(events))
        assert b.cycle_stats['phantom_only'] >= 1


def test_ninth_card_raises_and_rebuild_replay_is_deterministic():
    pr = dict(decks=[dict(cards=['Knight', 'Archers', 'Fireball', 'Zap', 'Giant', 'Musketeer', 'Skeletons',
                                 'Valkyrie'], frequency=1.)])
    cyc = cycle_belief_class(Belief, CFG, LAM)
    b = make(cyc, pr)
    with pytest.raises(ValueError, match='no train deck'):
        b.update(30, [PublicEvent(30, 'card', 'HogRider')])
    # replay of a conflicting history into a fresh instance gives the same rows (hidden plays are derived state)
    pr2, _, visible, _ = hidden_spell_case(3)
    events = [PublicEvent(t, 'card', n) for t, n in visible]
    x, y = make(cyc, pr2), make(cyc, pr2)
    for i in range(1, len(events) + 1):
        x.update(events[i-1].tick, events[:i])
    y.update(events[-1].tick, events)
    same(x, y)


def test_deadline_conflict_matches_unbounded():
    """A conflict inside s1's chunked (deadline) transaction falls back to the resolver from untouched state."""
    pr, _, visible, _ = hidden_spell_case(2)
    cyc = cycle_belief_class(Belief, CFG, LAM)
    events = [PublicEvent(t, 'card', n) for t, n in visible]
    x, y = make(cyc, pr), make(cyc, pr)
    for i in range(1, len(events) + 1):
        x.update(events[i-1].tick, events[:i], deadline=1e18)
        y.update(events[i-1].tick, events[:i])
    same(x, y)


def test_spec():
    assert parse_spec(None) is None and parse_spec('off') is None
    assert parse_spec('soft:eps=0.05,cap=1000')['cap'] == 1000
    with pytest.raises(ValueError):
        parse_spec('soft:bogus=1')


def test_ab_guard_streams(monkeypatch):
    """cyc-hard / cyc-soft view wrapper: a too-early repeat is dropped from the D1 rows in both modes; soft passes it to
    the belief events as 'card?' with P(real); a 9th distinct card is dropped in both."""
    from dataclasses import dataclass, field
    sys.path.insert(0, str(ROOT / 'reports/strategy_council_20260928/search-noise-s6'))
    from types import SimpleNamespace
    from bot.cyclemodel.ab import CycleGuardPlayer

    @dataclass(frozen=True)
    class Info:
        events: tuple = ()

    @dataclass(frozen=True)
    class View:
        info: Info
        public_events: list = field(default_factory=list)

    class Inner:
        def start(self, ctx):
            self.seen = []

        def act(self, view):
            self.seen.append(view)

        def close(self):
            pass

    cards = {n: dict(units=[dict(**{'class': 'Troop'})]) for n in COSTS}
    rt = SimpleNamespace(R=SimpleNamespace(costs=COSTS, config=dict(cards=cards)))
    seq = [(100, 'Knight'), (160, 'Archers'), (220, 'Giant'), (280, 'Knight'),        # Knight again after 2: conflict
           (340, 'Musketeer'), (400, 'Valkyrie'), (460, 'Skeletons'), (520, 'Goblins'), (580, 'Bomber'),
           (640, 'Minions')]                                                          # Minions = 9th distinct
    for mode in ('hard', 'soft'):
        inner = Inner()
        p = CycleGuardPlayer(rt, inner, mode, f'cyc-{mode}:x')
        p.start(SimpleNamespace(seat=0))
        evs = [PublicEvent(t, 'card', n) for t, n in seq]
        rows = [dict(seat=1, tick=t, kind='card', name=n, amount=0., x=9., y=24.) for t, n in seq]
        rows.insert(2, dict(seat=0, tick=150, kind='card', name='Zap', amount=0., x=9., y=8.))
        for k in range(1, len(seq) + 1):        # prefix-stable polling, as play_match
            p.act(View(Info(tuple(evs[:k])), [r for r in rows if r['tick'] <= seq[k-1][0]]))
        last = inner.seen[-1]
        d1 = [(r['tick'], r['name']) for r in last.public_events if r['seat'] == 1]
        assert (280, 'Knight') not in d1 and (640, 'Minions') not in d1 and len(d1) == 8
        assert any(r['seat'] == 0 for r in last.public_events)
        soft = [e for e in last.info.events if e.kind == 'card?']
        if mode == 'hard':
            assert not soft and len(last.info.events) == 8
        else:
            assert [(e.tick, e.name) for e in soft] == [(280, 'Knight')] and 0. < soft[0].amount < 1.
        assert p.counts['cyc_conflicts'] == 1 and p.counts['cyc_ninth'] == 1


ONE = dict(decks=[dict(cards=['Knight', 'Archers', 'Fireball', 'Zap', 'Giant', 'Musketeer', 'Skeletons', 'Valkyrie'],
                       frequency=1.)])


def test_hidden_cost_is_a_weighted_average():
    """Sol r1 #2: two hidden plays of known cost must average to the cost sum, whatever lam is."""
    cyc = cycle_belief_class(Belief, CFG, {n: 0.1 for n in COSTS})
    b = make(cyc, ONE)
    b.update(1, [])
    s = b._force_refills(b.states[:50])
    w = np.ones(len(s))
    lam, cost = b._lam_cost()
    s2, w2, c2 = b._hide(s, w, np.zeros(len(s)), 2, 1e9)
    avg = c2 / w2
    assert avg.min() >= 2 * min(COSTS[n] for n in ONE['decks'][0]['cards']) - 1e-9
    assert avg.max() <= 2 * max(COSTS[n] for n in ONE['decks'][0]['cards']) + 1e-9


def test_soft_p1_at_pending_refill_and_floor_survivor():
    """Sol r1 #1/#6: 'card?' with p = 1 right after a play (pending refill) is recorded, never routed to the frozen
    'card' path; an aggressive floor never empties the belief."""
    for spec in ('soft', 'soft:floor=0.5'):
        cyc = cycle_belief_class(Belief, parse_spec(spec), LAM)
        b = make(cyc, ONE)
        ev = [PublicEvent(400, 'card', 'Knight'), PublicEvent(401, 'card?', 'Knight', 1.0)]
        b.update(400, ev[:1])
        b.update(401, ev)
        assert b.events == ev and len(b.states) >= 1
        b.sample(np.random.default_rng(0))
        ev.append(PublicEvent(402, 'card?', 'Archers', 0.4))
        b.update(402, ev)
        assert len(b.states) >= 1 and abs(b.cumulative[-1] - b.weights.sum()) < 1e-9


def test_unaffordable_k0_rejected_and_log_reset():
    """Sol r1 #5/#7: a conflict whose card the ledger + slack cannot pay is not explained; a full replay (rebuild)
    clears stale explanation stats."""
    cyc = cycle_belief_class(Belief, parse_spec('soft:slack=0'), LAM)
    b = make(cyc, ONE)
    ev = [PublicEvent(40, 'card', 'Giant'), PublicEvent(41, 'card', 'Giant')]   # ledger ~1.0 < 5
    b.update(41, ev)
    assert b.cycle_stats['rejected'] == 1
    DerivedPublicState.__init__(b, ONE, COSTS)
    b.update(40, ev[:1])
    assert b.cycle_stats['rejected'] == 0
    with pytest.raises(ValueError):
        parse_spec('soft:cap=0')
