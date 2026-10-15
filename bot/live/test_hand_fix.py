"""Own hand/cycle sanitising (OwnTracker) and search-failure stat propagation (LivePlayer) tests.

    PYTHONPATH=. CLASHER_BOT_RUNTIME=... CLASHER_LIVE_FAST=student:<it5s2.pt>@0.5375 \
        nice -n 19 taskset -c 2-5 python -m pytest -q bot/live/test_hand_fix.py

The OwnTracker tests need only numpy and the frozen own_cycle (parity); the translator, session, player and game
tests need the frozen runtime (~15 s setup) and the it5s2 checkpoint (~2 min, 4 cores).
"""
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
D = ['Knight', 'Archers', 'Giant', 'Musketeer', 'MiniPekka', 'Fireball', 'Arrows', 'Goblins']


def tracker(order=D, known=5):
    from bot.live.translate import OwnTracker
    t = OwnTracker(D)
    t.reset(order, known)
    return t


def ok(own):
    from bot.live.translate import own_invariant_breaks
    assert own_invariant_breaks(own, D) == [], own
    return own


# -- the four HUD faults ----------------------------------------------------------------------------------------
def test_duplicate_slot_keeps_the_tracked_card():
    t = tracker()
    own = ok(t.own(100, 5., ['Knight', 'Knight', 'Giant', 'Musketeer'], 'MiniPekka'))
    assert own['hand'] == D[:4] and own['cycle'] == D[4:]
    assert t.stats['own_fix:duplicate'] == 1 and t.stats['own_fix'] == 1 and t.stats['own_fix_frames'] == 1


def test_off_deck_slot_keeps_the_tracked_card():
    t = tracker()
    own = ok(t.own(100, 5., ['Knight', 'Archers', 'Valkyrie', 'Musketeer'], 'MiniPekka'))
    assert own['hand'] == D[:4] and t.stats['own_fix:off_deck'] == 1


def test_next_equal_to_a_held_card_is_the_tracked_next():
    t = tracker()
    own = ok(t.own(100, 5., D[:4], 'Giant'))
    assert own['cycle'][0] == 'MiniPekka' and 'Giant' not in own['cycle']
    assert t.stats['own_fix:next_in_hand'] == 1


def test_missing_slot_is_filled_from_the_tracker():
    t = tracker()
    own = ok(t.own(100, 5., ['Knight', None, 'Giant'], None))      # one slot unread, one absent, no next
    assert own['hand'] == D[:4] and own['cycle'] == D[4:]
    assert t.stats['own_fix:missing'] == 2 and t.stats['own_fix:next_missing'] == 1


def test_a_slot_changes_only_after_our_play_of_it():
    """A plausible wrong card (a cycle card) never replaces a held card; our play empties its slot, the next card
    refills it (engine dynamics), and the cycle keeps the played card at its back: 4 + 4, or 3 + 5 in a refill."""
    t = tracker()
    ok(t.own(100, 5., ['Knight', 'Fireball', 'Giant', 'Musketeer'], 'MiniPekka'))
    assert t.hand == D[:4] and t.stats['own_fix:slot'] == 1
    t.play(100, 'Archers')
    own = ok(t.own(100, 5., ['Knight', None, 'Giant', 'Musketeer'], 'MiniPekka'))
    assert own['hand'] == ['Knight', None, 'Giant', 'Musketeer'] and own['cycle'] == D[4:] + ['Archers']
    own = ok(t.own(105, 5., ['Knight', 'MiniPekka', 'Giant', 'Musketeer'], 'Fireball'))
    assert own['hand'] == ['Knight', 'MiniPekka', 'Giant', 'Musketeer']
    assert own['cycle'] == ['Fireball', 'Arrows', 'Goblins', 'Archers'] and own['refill'] > 0


# -- parity and order learning ----------------------------------------------------------------------------------
def _frozen_cycle():
    from imitation.evaluation.paths import setup
    setup()
    from own_cycle import OwnCycle
    return OwnCycle


def _noisy(rng, hand, nxt, slot_err=.3, next_err=.1):
    hud = list(hand)
    if rng.random() < slot_err:
        hud[rng.randrange(4)] = rng.choice(D + ['Valkyrie', None])
    if rng.random() < next_err:
        nxt = rng.choice(D + [None])
    return hud, nxt


def test_exact_parity_with_the_frozen_own_cycle_under_heavy_hud_noise():
    """True order known (the PERC arms): output == the engine's own hand/cycle every frame, whatever the HUD reads
    (30% of frames with a random slot fault, 10% with a wrong next)."""
    OwnCycle = _frozen_cycle()
    rng = random.Random(0)
    fixes = 0
    for trial in range(40):
        order = D[:]
        rng.shuffle(order)
        oc, t, tick = OwnCycle(order), tracker(order), 0
        for _ in range(80):
            tick += rng.randint(1, 40)
            oc.advance(tick)
            if rng.random() < .4 and any(oc.hand):
                card = rng.choice([c for c in oc.hand if c])
                oc.play(tick, card)
                t.play(tick, card)
            tick += 1
            oc.advance(tick)
            own = ok(t.own(tick, 5., *_noisy(rng, oc.hand, oc.queue[0])))
            assert own['hand'] == list(oc.hand) and own['cycle'] == list(oc.queue) and own['refill'] == oc.refill
        fixes += t.stats['own_fix']
    assert fixes > 100


def test_unknown_queue_order_is_learned_from_the_hud():
    """LiveSession knows only hand + next; the other three come from the deck order. The HUD's next decides which
    unknown card comes first: after it is shown, the hand is right every frame at the measured noise."""
    OwnCycle = _frozen_cycle()
    rng = random.Random(1)
    wrong = Counter()
    for trial in range(100):
        order = D[:]
        rng.shuffle(order)
        oc, t, tick = OwnCycle(order), tracker(order[:5] + sorted(order[5:])), 0
        for _ in range(80):
            tick += 5
            oc.advance(tick)
            if rng.random() < .15 and any(oc.hand):
                card = rng.choice([c for c in oc.hand if c])
                oc.play(tick, card)
                t.play(tick, card)
            own = ok(t.own(tick, 5., *_noisy(rng, oc.hand, oc.queue[0], .046, .015)))
            wrong['hand'] += own['hand'] != list(oc.hand)
            wrong['next'] += own['cycle'][0] != oc.queue[0]
            wrong['frames'] += 1
    assert wrong['hand'] == 0 and wrong['next'] <= .002*wrong['frames'], wrong


def test_reanchor_on_a_persistent_valid_hud_and_on_a_play_the_tracker_lost():
    t = tracker()
    seen = ['Knight', 'Archers', 'Fireball', 'Musketeer']        # the guessed opening was wrong in slot 2
    for k in range(3):
        assert ok(t.own(100 + 5*k, 5., seen, 'MiniPekka'))['hand'] == D[:4]
    own = ok(t.own(115, 5., seen, 'MiniPekka'))                  # 4th identical valid reading
    assert own['hand'] == seen and own['cycle'][0] == 'MiniPekka' and t.stats['own_reanchor_hud'] == 1
    t2 = tracker()
    t2.own(100, 5., ['Knight', 'Archers', 'Arrows', 'Musketeer'], 'MiniPekka')
    t2.play(101, 'Arrows')                                        # no hypothesis holds Arrows: re-anchor, then play
    own = ok(t2.own(101, 5., ['Knight', 'Archers', None, 'Musketeer'], 'MiniPekka'))
    assert own['hand'] == ['Knight', 'Archers', None, 'Musketeer'] and own['cycle'][-1] == 'Arrows'
    assert t2.stats['own_reanchor_play'] == 1


# -- translator / session / player (frozen runtime) -------------------------------------------------------------
@pytest.fixture(scope='module')
def rt():
    from bot.players.runtime import Runtime
    return Runtime()


def test_translator_information_is_always_engine_valid(rt):
    """Through LiveTranslator.information: the packet's hand ids are the tracked hand + next, never the misread."""
    from test_live import record
    from bot.live.translate import LiveTranslator
    tr = LiveTranslator(rt, D, plays_from='events')
    tr.set_own_order(D)
    for tick, hand, nxt in ((600, ['Knight', 'Knight', 'Giant', 'Musketeer'], 'MiniPekka'),
                            (605, ['Knight', 'Archers', 'Valkyrie', 'Musketeer'], 'Giant'),
                            (610, [None, 'Archers', 'Giant'], None)):
        info = tr.information(record(tick=tick, events=[], hand=dict(cards=hand, next=nxt, probs=[.9]*4)))
        ok(info.own)
        ids = [int(x) for x in info.packet.observation.hand_ids[:5]]
        assert ids == [rt.R.builder.token_id(n) for n in D[:5]], (tick, ids)
    assert tr.stats['own_fix'] == 6 and tr.stats.get('own_invariant_break', 0) == 0


def test_hand_sanitising_is_fair_information_invariant(rt):
    """Opponent-private fields in a record (hand, elixir, deck, private ids) change nothing in our tracked own
    state, its correction counts, or the packet; the tracker reads only our deck, our HUD and our own plays."""
    from test_live import record
    from bot.live.translate import LiveTranslator
    hud = dict(cards=['Knight', 'Knight', 'Fireball', None], next='Giant', probs=[.8, .7, .9, .1])
    out = []
    for poison in (False, True):
        tr = LiveTranslator(rt, D, plays_from='events')
        tr.set_own_order(D)
        extra = dict(opponent=dict(hand=['Golem']*4, elixir=9.9, next='Rocket', deck=['Xbow']*8),
                     opp_hand=['Zap']*4, opp_next='Log') if poison else {}
        infos = [tr.information(record(tick=600 + 5*k, hand=hud, events=[], **extra)) for k in range(6)]
        out.append(([i.own for i in infos], {k: v for k, v in tr.stats.items() if k.startswith('own')},
                    [i.packet.observation.hand_ids.tolist() for i in infos]))
    assert out[0] == out[1]


class _OnePlay:
    """Stub player: plays slot 1 at the first actionable poll, then waits."""
    name, deadline_seconds = 'stub', None

    def start(self, ctx):
        self.done = False

    def act(self, view):
        from bot.players.base import Decision, WAIT
        if view.can_act and not self.done and view.info.own['hand'][1] is not None:
            self.done = True
            return Decision(576*1 + 5*18 + 4, stats={})
        return Decision(WAIT, stats={})

    def close(self):
        pass


def test_session_confirms_our_play_from_the_raw_hud_not_a_single_misread(rt):
    from test_live import record
    from bot.live.translate import LiveSession
    s = LiveSession(rt, _OnePlay(), D, seed=7)
    hand0 = dict(cards=D[:4], next='MiniPekka')
    t = 90
    while not s.ch.submitted:
        s.step(record(tick=t, events=[], elixir=10., hand=hand0))
        t += 5
    assert s.ch.pending and s.ch.pending[0].card == 'Archers'
    # one misread frame of the reserved slot (a cycle card) does not complete the command
    s.step(record(tick=t, events=[], elixir=10., hand=dict(cards=['Knight', 'Arrows', 'Giant', 'Musketeer'], next='MiniPekka')))
    t += 5
    s.step(record(tick=t, events=[], elixir=10., hand=hand0))
    t += 5
    assert s.ch.pending and not s.tr.plays[0]
    # the slot really refills: two consecutive polls of evidence -> our play enters this poll's own state
    after = dict(cards=['Knight', 'MiniPekka', 'Giant', 'Musketeer'], next='Fireball')
    for _ in range(2):
        s.step(record(tick=t, events=[], elixir=10., hand=after))
        t += 5
    assert [n for _, n in s.tr.plays[0]] == ['Archers'] and not s.ch.pending
    assert s.tr.stats['own_play_confirmed_by_hud'] == 1
    info = s.tr.information(record(tick=t, events=[], elixir=10., hand=after))
    assert info.own['hand'] == after['cards'] and info.own['cycle'] == ['Fireball', 'Arrows', 'Goblins', 'Archers']
    s.close()


def test_session_waits_for_a_distinct_opening_hand(rt):
    from test_live import record
    from bot.live.translate import LiveSession
    s = LiveSession(rt, _OnePlay(), D, seed=7)
    s.step(record(tick=90, events=[], hand=dict(cards=['Knight', 'Knight', 'Giant', 'Musketeer'], next='MiniPekka')))
    assert not s.started and s.tr.stats['opening_hand_waits'] == 1
    s.step(record(tick=95, events=[], hand=dict(cards=D[:4], next='MiniPekka')))
    assert s.started and list(s.ctx.own_order[:5]) == D[:5]
    s.close()


def test_native_failure_and_other_failure_fields_reach_the_decision_stats(rt):
    """lopp_fast reports native_failure (main 654b18bb) in the search stats; LivePlayer keeps it (and any other
    failure-named field) in its decision stats / LiveSession.log, and counts it per match."""
    from bot.players.base import Decision, SEARCH_INTERVAL, WAIT
    from bot.live.player import LivePlayer, search_stats
    from test_live import _play_with
    bot = LivePlayer(rt, tier='search', wall_ms=150, threads=1)

    def failing(view, wall0=None, default=None):
        if not view.can_act or view.tick % SEARCH_INTERVAL:
            return Decision(WAIT, stats=None)
        return Decision(default if default is not None else WAIT, 0,
                        dict(hit=True, fallback=True, completed=0, candidates=5, native_failure='native_pool',
                             pool_dead_workers=1, native=7, learned=0, phase_ms={'x': 1.}, wall_seconds=.01))
    bot.search.act = failing
    _play_with(rt, bot, ticks=400)
    fails = [d for d in bot.decisions if d.get('native_failure')]
    assert fails and all(d['native_failure'] == 'native_pool' and d['pool_dead_workers'] == 1 for d in fails)
    assert fails[-1]['native_failures'] == len(fails) == bot.native_failures['native_pool']
    assert all(d['source'] == 'default-it5s2' and d['native_rollouts'] == 7 and 'phase_ms' not in d for d in fails)
    assert search_stats(dict(hit=False, new_failure_kind='x', broken_pool=True)) == dict(
        hit=False, new_failure_kind='x', broken_pool=True)


def test_root_state_breaks_flag_both_players():
    from bot.live.player import root_state_breaks

    class Info:
        own = dict(hand=['Knight', 'Knight', 'Giant', 'Musketeer'], cycle=D[4:] + ['Archers'])
    opp = dict(hand=['Zap', None, 'Log', 'Golem'], cycle=['Rocket', 'Xbow', 'Tesla', 'Miner', 'Bats'])
    assert root_state_breaks(Info, opp) == dict(own_state_break=2, own_state_breaks='hand_duplicate,cycle')
    Info.own = dict(hand=D[:4], cycle=D[4:])
    assert root_state_breaks(Info, dict(opp, cycle=opp['cycle'][:4])) == dict(opp_state_break=1, opp_state_breaks='cycle')


def test_perc_emp_game_own_state_is_exact_and_opponent_samples_are_valid(rt):
    """PERC-emp (measured HUD noise): every own state the bot sees equals the engine's true own hand/cycle, and
    every opponent belief sample on the translator's event stream satisfies the root builder's cycle rules."""
    from bot.players.ours import play_match, x4s_setup
    from bot.live.player import make_live_player, live_belief_class
    from bot.live.translate import deck_state_breaks
    from test_live import BASE
    case = x4s_setup(rt, 0, BASE)
    bot = make_live_player(rt, 'PERC-emp:LIVE-fast-it5s2')
    seen = []
    inner_act = bot.inner.act

    def spy(view):
        seen.append((view.tick, view.info.own, view.info.events))
        return inner_act(view)
    bot.inner.act = spy
    true = {}
    outer_act = bot.act

    def truth(view):
        true[view.tick] = view.info.own
        return outer_act(view)
    bot.act = truth
    play_match(rt, {case['seat']: bot, 1-case['seat']: make_live_player(rt, 'v1')},
               seed=case['seed'], decks=case['decks'], max_ticks=2400)
    assert len(seen) > 400 and bot.errors == 0
    exact = sum(own['hand'] == list(true[t]['hand']) and own['cycle'] == list(true[t]['cycle']) for t, own, _ in seen)
    assert exact == len(seen), (exact, len(seen))
    assert bot.tr.stats['own_fix'] > 0 and bot.tr.stats.get('own_invariant_break', 0) == 0
    from fair_player import PublicPlanner
    p = PublicPlanner(rt.R, rt.PRIOR, 0)
    p.belief.__class__ = live_belief_class()
    p.belief.human_prior = rt.PRIOR
    rng = np.random.default_rng(0)
    restarts, last, t_last = 0, (), 0
    for k, (t, _, events) in enumerate(seen):
        new = events[len(last):]
        if tuple(events[:len(last)]) != tuple(last) or any(e.tick < t_last for e in new):
            p = PublicPlanner(rt.R, rt.PRIOR, 0)       # resync rewrote the history: the player restarts too
            p.belief.__class__ = live_belief_class()
            p.belief.human_prior = rt.PRIOR
            restarts += 1
        p.belief.update(t, events)
        last, t_last = events, t
        if k % 4 == 0:
            for _ in range(3):
                assert deck_state_breaks(p.belief.sample(rng)) == []
