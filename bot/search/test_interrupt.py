"""Unit tests for bot/search/interrupt.py (the -wint arm) and its name parsing (bot lead live-diag)."""
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np

from bot.players.base import Decision, PublicView, WAIT
from bot.search import interrupt
from bot.search.interrupt import Interruptible


def packet(enemies_on_our_half):
    n = enemies_on_our_half + 1                      # + one enemy tower (never counted)
    f = np.zeros((n, 10), dtype=np.float32)
    ids = np.zeros(n, dtype=np.int64)
    f[0, 3], f[0, 5], f[0, 1], ids[0] = 1, 1, 0.1, 0     # tower token
    for i in range(1, n):
        f[i, 3], f[i, 4], f[i, 1], ids[i] = 1, 1, 0.2, 2  # enemy troop, y = 6.4 < 16
    return SimpleNamespace(observation=SimpleNamespace(entity_mask=np.ones(n, bool), entity_features=f, entity_ids=ids))


RT = SimpleNamespace(R=SimpleNamespace(builder=SimpleNamespace(token_names=['Tower', 'KingTower', 'Knight'])))


class FakeLive:
    def __init__(self, script):
        self.name, self.deadline_seconds, self.search_disabled = 'LIVE-x', .2, False
        self.script, self.calls = list(script), []

    def start(self, ctx):
        self.ctx = ctx

    def act(self, view):
        self.calls.append((view.tick, view.can_act))
        if not view.can_act:
            return Decision(WAIT, 0, None)
        return self.script.pop(0)

    def close(self):
        pass


def view(tick, enemies=0, events=(), can_act=True):
    return PublicView(tick, 0, SimpleNamespace(packet=packet(enemies)), None, list(events), (), can_act)


def test_timed_wait_not_handed_to_session_and_blocks_until_expiry():
    live = FakeLive([Decision(WAIT, 20, {'source': 'search'}), Decision(100, 0, {'source': 'search'})])
    w = Interruptible(RT, live)
    w.start(SimpleNamespace(seat=0))
    d = w.act(view(10))
    assert d.wait_ticks == 0 and d.stats['timed_wait'] == 20
    for t in (15, 20, 25):                            # inside the wait, nothing new: blocked, inner polled can_act False
        b = w.act(view(t))
        assert b.action == WAIT and b.stats is None
    assert live.calls[1:] == [(15, False), (20, False), (25, False)]
    d2 = w.act(view(30))                              # wait over: decides
    assert d2.action == 100


def test_new_enemy_card_interrupts_at_next_search_tick():
    live = FakeLive([Decision(WAIT, 40, {'source': 'search'}), Decision(7, 0, {'source': 'search'})])
    w = Interruptible(RT, live)
    w.start(SimpleNamespace(seat=0))
    w.act(view(10))
    card = {'seat': 1, 'kind': 'card', 'name': 'Knight'}
    b = w.act(view(15, events=[card]))                # off a 10-tick search tick: interrupt noted, still blocked
    assert b.action == WAIT and b.stats is None and w.interrupts == 1
    d = w.act(view(20, events=[card]))
    assert d.action == 7


def test_enemy_unit_growth_interrupts():
    live = FakeLive([Decision(WAIT, 40, {'source': 'search'}), Decision(8, 0, {'source': 'search'})])
    w = Interruptible(RT, live)
    w.start(SimpleNamespace(seat=0))
    w.act(view(10, enemies=1))
    assert w.act(view(20, enemies=1)).stats is None   # same count: blocked
    assert w.act(view(30, enemies=2)).action == 8     # one more enemy unit on our half


def test_search_disabled_forwarded():
    live = FakeLive([])
    w = Interruptible(RT, live)
    w.search_disabled = True
    assert live.search_disabled is True


def test_lopp_serial_name_parsing(monkeypatch):
    import bot.search.lopp as lopp
    built = []

    class FakeOpp:
        def __init__(self, rt, arm=None, name=None, **kw):
            self.name, self.arm, self.deadline_seconds = name, arm, None
            built.append(name)
    monkeypatch.setattr(lopp, 'LearnedOppPlayer', FakeOpp)
    p = lopp.make_lopp_player(RT, 'K4L-R-gs-res-wint')
    assert isinstance(p, Interruptible) and p.name == 'K4L-R-gs-res-wint' and built == ['K4L-R-gs-res']
    q = lopp.make_lopp_player(RT, 'K4L-R-gs-res')
    assert not isinstance(q, Interruptible)


def test_live_name_parsing(monkeypatch):
    import bot.live.player as player
    import bot.search.lopp as lopp
    from bot.search import lopp_fast

    class FakeSearch:
        deadline_seconds, threads = .2, 4

    class FakeLivePlayer:
        def __init__(self, rt, **kw):
            self.name, self.deadline_seconds, self.kw = kw['name'], .2, kw
    monkeypatch.setattr(lopp, 'make_lopp_player', lambda rt, body: FakeSearch())
    monkeypatch.setattr(player, 'LivePlayer', FakeLivePlayer)
    p = lopp_fast.make_live_lopp(RT, 'LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-wint')
    assert isinstance(p, Interruptible) and isinstance(p.live, FakeLivePlayer)
    assert p.name == 'LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-wint'
    q = lopp_fast.make_live_lopp(RT, 'LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res')
    assert isinstance(q, FakeLivePlayer) and q.name == 'LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res'
