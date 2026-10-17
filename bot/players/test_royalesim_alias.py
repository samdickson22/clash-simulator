"""The RoyaleSim loop applies the native loop's per-seat alias contract."""
from contextlib import nullcontext
from types import ModuleType, SimpleNamespace
import sys

import pytest

from bot.players.base import Decision
from bot.players import royalesim_match


@pytest.mark.parametrize('alias_seat', [None, 0, 1])
@pytest.mark.parametrize('with_observer', [False, True])
def test_alias_before_reservation_and_both_event_streams(monkeypatch, alias_seat, with_observer):
    calls = []
    raw = [SimpleNamespace(packet=object(), events=('MegaMinion',)) for _ in range(2)]
    aliased = SimpleNamespace(packet=object(), events=('Minions',))
    public = [{'seat': 1, 'kind': 'card', 'name': 'MegaMinion'}]
    mapped = [{'seat': 1, 'kind': 'card', 'name': 'Minions'}]

    class Alias:
        def info(self, info):
            assert info is raw[alias_seat]
            calls.append('alias-info')
            return aliased

        def recorder(self, rows):
            assert rows is public
            calls.append('alias-recorder')
            return mapped

    class Player:
        name = 'test'
        deadline_seconds = .01

        def start(self, ctx):
            self.seat = ctx.seat
            # The alias becomes available only after start, just like AliasedPlayer.
            self.observe_alias = Alias() if ctx.seat == alias_seat else None

        def act(self, view):
            expected = aliased if self.seat == alias_seat else raw[self.seat]
            assert view.info is expected
            assert view.reserved is expected.packet
            assert view.public_events is (mapped if self.seat == alias_seat else public)
            calls.append(('act', self.seat))
            return Decision(stats={'source': 'test'})

        def close(self):
            pass

    class Queue:
        def __init__(self, *args):
            self.pending = []
            self.available = True
            self.blocked = 0

        def ready(self, tick):
            return False

        def own_packet(self, info, builder):
            calls.append(('reserve', info))
            return info.packet

        def diagnostics(self):
            return {}

    class Match:
        def __init__(self, *args, **kwargs):
            self.decks = [['Knight'] * 8 for _ in range(2)]
            self.public_events = public
            self.tick = 90
            self.state = dict(game_over=False, tick=90, winner=2,
                              players=[dict(crowns=0, tower_hp=[]) for _ in range(2)])
            self.command_phase = SimpleNamespace(receipt=lambda: {}, closed=lambda _: False)
            self.b = SimpleNamespace(step=lambda *_: None, state_hash=lambda: 'test')
            self.tr = SimpleNamespace(stats={})
            self.own = {a: SimpleNamespace(mismatch={}) for a in (0, 1)}

        def information(self, seat):
            return raw[seat]

        def refresh(self):
            self.state['game_over'] = True
            self.state['tick'] = 95

    def lateness(ch, waits, available_at, actor, *args):
        calls.append(('lateness', actor))
        return None, 0

    def observer(view, decision):
        assert calls[-1] == ('lateness', view.seat)
        assert decision.stats == {'source': 'test'}
        calls.append(('observer', view.seat))

    modules = {
        'clasher.analysis.loss_review.delay_fixes': dict(CommandQueue=Queue),
        'latency': dict(apply_lateness=lateness),
        'gc_window': dict(WINDOW=nullcontext()),
        'royalesim': {},
    }
    for name, attrs in modules.items():
        module = ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(royalesim_match, 'RsimMatch', Match)
    monkeypatch.setattr(royalesim_match, 'rs_version', lambda: 'test')
    rt = SimpleNamespace(R=SimpleNamespace(builder=object()))
    result = royalesim_match.play_match(rt, {a: Player() for a in (0, 1)},
                                        seed=1, decks=[[], []], vocab={'test': True},
                                        observer=observer if with_observer else None)
    assert result['terminal']
    assert raw[0].events == raw[1].events == ('MegaMinion',)
    assert public[0]['name'] == 'MegaMinion'
    assert [c for c in calls if isinstance(c, tuple) and c[0] == 'observer'] == (
        [('observer', 0), ('observer', 1)] if with_observer else [])
    if alias_seat is None:
        assert 'alias-info' not in calls and 'alias-recorder' not in calls
    else:
        assert calls.index('alias-info') < calls.index(('reserve', aliased))
        assert calls.index('alias-recorder') < calls.index(('act', alias_seat))
