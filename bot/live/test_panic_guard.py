"""Native-panic guards (LIVE track): card-consistent boards (translator) and the BaseException fallback (LivePlayer).

    PYTHONPATH=. CLASHER_BOT_RUNTIME=... CLASHER_LIVE_FAST=student:<it5s2.pt>@0.5375 \
        [CLASHER_LOPP_MODELS=<dir with pool.npz>] nice -n 19 taskset -c 2-5 python -m pytest -q bot/live/test_panic_guard.py

Found 2026-10-15 (PERC-emp:LIVE-K4L-R-gs-rw-fc-w200-t4-p4 on 03): empirical card noise put an own-side ElectroSpirit
(a FireSpirits/false-positive misread) into the search root; under lopp_fast 'fc' the root's config holds only the
cards in both players' hands/cycles, so c56.rs:265 (electro_land: config.cards[key].chain) panics, and the
pyo3 PanicException (a BaseException) escaped LivePlayer's `except Exception`. See reports/live/integration/PANIC-FIX.md.
The K4L pool test needs the opponent nets (CLASHER_LOPP_MODELS) and is skipped without them.
"""
import importlib
import os
from pathlib import Path

import numpy as np
import pytest

from test_live import BASE, OWN, _play_with

ES_UNITS = lambda k: [dict(card='ElectroSpirit', owner=0, x=9.5, y=15.0 + .1*k, hp_frac=1., score=.9),
                      dict(card='Knight', owner=1, x=9.5, y=18.0 - .1*k, hp_frac=1., score=.9)]


@pytest.fixture(scope='module')
def rt():
    from bot.players.runtime import Runtime
    return Runtime()


def _feed(rt, sanitize, units=ES_UNITS):
    from bot.live.translate import LiveTranslator
    tr = LiveTranslator(rt, OWN, plays_from='events')
    tr.sanitize = sanitize
    for k, t in enumerate(range(600, 625, 5)):
        info = tr.information(dict(tick=t, elixir=5.0, hand=dict(cards=OWN[:4], next=OWN[4]), towers=[],
                                   units=units(k),
                                   events=[dict(owner=1, card='Knight', x=9.5, y=20.5, tick=560)] if k == 0 else []))
    return tr, info


def _fc_root(rt, info):
    """The search root as K4L 'fc' builds it: R.root on a belief sample, config cut to the hand+cycle cards
    (lopp_fast.ConfigCache, exactly what the pool workers parse; the threaded path's _ConfigJson cuts the same)."""
    from fair_player import PublicPlanner
    from bot.search.lopp_fast import ConfigCache, split_snapshot
    R = rt.R
    p = PublicPlanner(R, rt.PRIOR, 1)
    p.belief.update(info.tick, info.events)
    opp = p.belief.sample(np.random.default_rng(0))
    root = R.root(info, opp, np.random.default_rng(1))
    head, cfg, tail = split_snapshot(root.snapshot())
    state = importlib.import_module(type(R.native).__module__).BattleState
    return root, state(ConfigCache(cfg).payload(head, tail)), opp


def _rollout(rt, state):
    from bot.search.oppmodel import STYLES
    return rt.R.native.rollout_e1(state.clone(), 0, 2304, STYLES[0], 27, 27, 200, 5, 0., 1e6)


def _panic_class(rt):
    """The real pyo3_runtime.PanicException (from the unsanitized crafted root), or None if the native no longer
    panics there (the bot lead's total lookup)."""
    _, info = _feed(rt, False)
    _, cut, _ = _fc_root(rt, info)
    try:
        _rollout(rt, cut)
    except BaseException as ex:          # noqa: B036 - the point of the test
        return type(ex)
    return None


def test_unsanitized_off_deck_unit_panics_the_fc_root(rt):
    """Regression: the crash path itself. Own deck lacks ElectroSpirit; the belief's sample lacks it; fc root ->
    PanicException, which is NOT an Exception (why `except Exception` missed it). The full-config root is fine."""
    _, info = _feed(rt, False)
    root, cut, opp = _fc_root(rt, info)
    assert 'ElectroSpirit' not in OWN + opp['hand'] + opp['cycle']
    _rollout(rt, root)                                   # full config: has the ElectroSpirit entry
    try:
        _rollout(rt, cut)
    except BaseException as ex:          # noqa: B036
        assert type(ex).__name__ == 'PanicException' and not isinstance(ex, Exception)
        assert 'no entry found for key' in str(ex)
    else:
        pytest.skip('this native pin no longer panics on a config-less ElectroSpirit (total lookup)')


def test_sanitizer_drops_off_deck_units_and_the_root_runs(rt):
    tr, info = _feed(rt, True)
    assert tr.stats['board_dropped:0:ElectroSpirit'] == 5 and tr.stats['board_dropped'] == 5
    root, cut, _ = _fc_root(rt, info)
    assert _rollout(rt, cut) == _rollout(rt, root)        # fc root runs and equals the full-config root


def test_board_rule_is_the_deck_rule(rt):
    """Own: our 8 cards only. Opponent: revealed cards, or any card while < 8 are revealed; a 9th card is dropped."""
    from bot.live.translate import LiveTranslator
    tr = LiveTranslator(rt, OWN, plays_from='events')
    assert tr.board_card_ok('Knight', 0) and not tr.board_card_ok('ElectroSpirit', 0)
    assert tr.board_card_ok('ElectroSpirit', 1) and tr.stats['board_unrevealed_opp_kept'] == 1
    eight = ['Golem', 'Xbow', 'Rocket', 'GoblinBarrel', 'Lightning', 'Tornado', 'MightyMiner', 'Goblinstein']
    tr.plays[1][:] = [(100 + i, c) for i, c in enumerate(eight)]
    assert tr.board_card_ok('Golem', 1) and not tr.board_card_ok('ElectroSpirit', 1)
    assert tr.stats['board_dropped:1:ElectroSpirit'] == 1 and tr.stats['board_dropped:0:ElectroSpirit'] == 1


def test_sanitizer_is_fair_information_invariant(rt):
    """Opponent-private keys (its deck/hand) change neither what is dropped nor the packet."""
    a, ia = _feed(rt, True)
    b, ib = _feed(rt, True, units=lambda k: [dict(u, private_card_id=26000000) for u in ES_UNITS(k)])
    assert dict(a.stats) == dict(b.stats)
    assert np.array_equal(ia.packet.observation.entity_features, ib.packet.observation.entity_features)


def test_perfect_perception_drops_nothing(rt):
    """Noise-free synthetic perception (PERC-events): every board unit is a card its owner has -> 0 drops."""
    from test_live import short_game
    for index in (0, 1):
        res, bot, case = short_game(rt, 'PERC-events:LIVE-fast-it5s2', index=index, ticks=1500)
        assert bot.tr.stats['board_dropped'] == 0 and bot.tr.stats['board_unrevealed_opp_kept'] >= 0
        assert res['plays'][case['seat']] > 0


def test_native_panic_in_search_falls_back_to_it5s2_then_disables(rt):
    """A PanicException (BaseException) from the search tier -> it5s2 decides ('fast-error'), counted in `panics`;
    max_errors consecutive -> search disabled. KeyboardInterrupt still propagates."""
    from bot.live.player import LivePlayer
    panic = _panic_class(rt)
    if panic is None:                    # native fixed: an equivalent BaseException stand-in
        panic = type('PanicException', (BaseException,), {})
    assert not issubclass(panic, Exception)
    bot = LivePlayer(rt, tier='search', wall_ms=150, threads=1, max_errors=2)

    def boom(*a, **k):
        raise panic('no entry found for key')
    bot.search.act = boom
    _play_with(rt, bot)
    srcs = [d['source'] for d in bot.decisions]
    assert srcs[:2] == ['fast-error', 'fast-error'] and set(srcs[2:]) <= {'fast-disabled'} and len(srcs) > 2
    assert all(d['action'] == d['fast_action'] for d in bot.decisions)
    assert bot.panics >= 2 and bot.decisions[1]['panics'] >= 2     # every caught panic, off-cadence polls too

    def interrupt(*a, **k):
        raise KeyboardInterrupt
    bot2 = LivePlayer(rt, tier='search', wall_ms=150, threads=1)
    bot2.search.act = interrupt
    with pytest.raises(KeyboardInterrupt):
        _play_with(rt, bot2)


def test_fast_tier_panic_is_caught(rt):
    from bot.live.player import LivePlayer
    panic = type('PanicException', (BaseException,), {})
    bot = LivePlayer(rt, tier='fast')

    def boom(*a, **k):
        raise panic('x')
    bot.fast.act = boom
    _play_with(rt, bot, ticks=300)
    assert bot.decisions and {d['source'] for d in bot.decisions} == {'fast-error'} and bot.panics > 0


MODELS = Path(os.environ.get('CLASHER_LOPP_MODELS', '/mpac/sdicks02/jobs/clasher/bot-lopp-models'))


@pytest.mark.skipif(not (MODELS / 'pool.npz').exists(), reason='no K4L opponent nets (CLASHER_LOPP_MODELS)')
def test_k4l_dead_pool_worker_keeps_falling_back(rt):
    """K4L p4: a pool worker that died (as after a panic in batch_rollouts) breaks every later search decision
    (BrokenPipe/EOF); the match continues on it5s2 and the search tier is disabled after max_errors. Runs last in
    this module: the pool is per process (lopp_fast._POOLS)."""
    from bot.live.player import make_live_player
    from bot.search import lopp_fast
    from bot.players.ours import play_match, x4s_setup
    case = x4s_setup(rt, 3, BASE)
    killed = []

    class KillAfter:
        """Kills one pool worker (a PID this test's pool started) at the 3rd search decision."""
        def __init__(self, inner):
            self.inner, self.n = inner, 0

        def __getattr__(self, k):
            return getattr(self.inner, k)

        def act(self, view, **kw):
            if view.can_act and view.tick % 10 == 0:
                self.n += 1
                if self.n == 3 and lopp_fast._POOLS:
                    proc = next(iter(lopp_fast._POOLS.values())).procs[0]
                    proc.kill()
                    proc.join(5)
                    killed.append(proc.pid)
            return self.inner.act(view, **kw)
    bot2 = make_live_player(rt, 'LIVE-K4L-R-gs-rw-fc-w200-t4-p4')
    bot2.search = KillAfter(bot2.search)
    bot2.max_errors = 3
    play_match(rt, {case['seat']: bot2, 1 - case['seat']: make_live_player(rt, 'v1')}, seed=case['seed'],
               decks=case['decks'], max_ticks=900)
    srcs = [d['source'] for d in bot2.decisions]
    assert killed, 'pool worker was never killed'
    k = srcs.index('fast-error')
    assert 'search' not in srcs[k:] and 'fast-disabled' in srcs[k:]     # never searches again; disabled
    assert all(d['action'] == d['fast_action'] for d in bot2.decisions[k:] if d['source'].startswith('fast'))
