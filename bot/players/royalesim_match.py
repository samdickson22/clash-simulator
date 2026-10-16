"""Play one match INSIDE RoyaleSim with two bot.players Players (any seat).

Mirrors bot/players/ours.py:play_match (= reports/explore/x4s/run.py:79-282) with the
physics swapped for RoyaleSim 0.1.34:
- same decks in the same initial order (x4s_setup; RoyaleSim shuffle=0 deals deck[:4] as the
  hand and deck[4:] as the queue, like ours), card and tower level 11, 5 starting elixir;
- the same harness-side lag: per-seat CommandQueue(27, capacity 1) with reservation; a play
  reserved at tick t is sent to RoyaleSim at t+27 with RoyaleSim's own delay set to 0, so
  RoyaleSim validates it in full at execution like our apply_action; a rejection is recorded
  and not refunded (nothing was debited);
- the same polling: every seat every 5 ticks from tick 90 (blocked polls included, the
  policy cadence needs them), search on 10-tick multiples, timed waits, abilities never
  pressed, honest lateness for wall-deadline players, GC deferral, the same command hash;
- the public event stream from the commands the harness applied (opponent card plays with
  the tile where RoyaleSim put them), never from RoyaleSim's opponent player record.
Players see the fair public view built by royalesim_translate.Translator. The search player
still plans on OUR Rust engine from that view (R.root): the intended model-mismatch setting.

Result scoring is RoyaleSim's own: crowns, three-crown end, 3 min + 2 min overtime, then its
weakest-tower tie-break (15.535 arm: the client's HP drain, which can run past tick 6000).
`winner` None = draw. Default rules: client_arms('15.535.29'); client='16.402' for current.

Engine time is advanced event to event (polls, due commands), so state_json is decoded about
once per 5 ticks; RoyaleSim stops a step early when the battle ends.
"""
from __future__ import annotations

import hashlib
import json
import time

from .base import MatchContext, PublicView, POLICY_INTERVAL, START_TICK, WAIT
from .royalesim_adapter import action_to_command, royalesim_card

# Both engines start a side at 6 elixir: ours (PlayerState default) and RoyaleSim's measured
# match.START_MANA (calibration.json: 60/60 recorded sides). The API example's 5000 is not the game.
START_ELIXIR_MILLI = 6000
MAX_TICKS = 7200        # safety cap: regulation+overtime end at 6000, the HP drain shortly after


class RsimMatch:
    """RoyaleSim battle + per-seat public bookkeeping; reusable by tests and cross-checks."""

    def __init__(self, rt, vocab, decks, seed, *, client='15.535.29', levels=None, tower_levels=None):
        from .royalesim_vocab import rsim_battle
        from .royalesim_translate import Translator, OwnCycleView
        self.b = rsim_battle(client)
        self.client = client
        catalogue = json.loads(self.b.catalogue_json())
        self.ids = {row[0]: i for i, row in enumerate(catalogue)}
        self.names = [row[0] for row in catalogue]
        self.decks = [list(d) for d in decks]
        self.b.set_command_delay_ticks(0, 0)
        self.b.reset(seed=int(seed) % (1 << 64), decks=[[self.ids[royalesim_card(c)] for c in d] for d in self.decks],
                     shuffle=0, start_tick=0, elixir_milli=[START_ELIXIR_MILLI]*2, tower_hp=None, spawns=[],
                     **self.level_args(levels, tower_levels))
        self.tr = Translator(rt, vocab, catalogue)
        self.tr.bind(self.b)
        self.own = {a: OwnCycleView(self.decks[a]) for a in (0, 1)}
        self.plays = {0: [], 1: []}             # accepted public plays (tick, name)
        self.events = {0: [], 1: []}            # PublicEvent stream each seat sees (enemy plays)
        self.public_events = []                 # recorder rows, both seats (D1 input)
        self.refresh()

    def level_args(self, levels, tower_levels):
        """levels: [{card: level} per seat] (bot/levels; missing cards 11), tower_levels: [seat0, seat1]. None (the
        default) passes nothing, so reset is the unchanged level-11 call."""
        out = {}
        if levels is not None:
            out['levels'] = [[int(levels[a].get(c, 11)) for c in self.decks[a]] for a in (0, 1)]
        if tower_levels is not None:
            out['tower_levels'] = [int(t) for t in tower_levels]
        return out

    def refresh(self):
        self.state = json.loads(self.b.state_json())
        return self.state

    @property
    def tick(self):
        return self.state['tick']

    def own_hud(self, seat):
        from .royalesim_adapter import our_card
        me = self.state['players'][seat]        # own record only
        hand = [our_card(self.names[c]) if c >= 0 else None for c in me['hand']]
        nxt = our_card(self.names[me['next_card']]) if me['next_card'] >= 0 else None
        return self.own[seat].own(self.tick, me['elixir_milli']/1000., hand, nxt)

    def information(self, seat):
        return self.tr.information(self.state, seat, self.own_hud(seat), self.plays, self.events[seat])

    def hand_card(self, seat, slot):
        from .royalesim_adapter import our_card
        c = self.state['players'][seat]['hand'][slot]
        return our_card(self.names[c]) if c >= 0 else None

    def execute(self, commands):
        """commands: [(seat, action, card)] due now. Applied in one RoyaleSim step of 0 ticks."""
        from derived_public_state import PublicEvent
        sent = [action_to_command(action, seat) for seat, action, _ in commands]
        rows = self.b.step(sent, 0)
        out = []
        for (seat, action, card), row in zip(commands, rows):
            ok = row[1] == 0
            if ok:
                tick = self.tick
                self.plays[seat].append((tick, card))
                self.own[seat].play(tick, card)
                self.events[1-seat].append(PublicEvent(tick, 'card', card))
                self.public_events.append(dict(seat=seat, tick=tick, kind='card', name=card, amount=0.,
                                               x=row[3]/18000., y=row[4]/18000.))
            out.append((ok, row[1]))
        self.refresh()
        return out


def play_match(rt, players, *, seed, decks, vocab=None, client='15.535.29', max_ticks=MAX_TICKS,
               delay=27, capacity=1, verbose=False, levels=None, tower_levels=None):
    """players: {0: Player, 1: Player}; decks: [deck_seat0, deck_seat1] in initial order."""
    from clasher.analysis.loss_review.delay_fixes import CommandQueue
    from latency import apply_lateness
    from gc_window import WINDOW
    from .royalesim_vocab import load
    import royalesim as rs
    R = rt.R
    m = RsimMatch(rt, vocab or load(rt), decks, seed, client=client, levels=levels, tower_levels=tower_levels)
    for a in (0, 1):
        if hasattr(players[a], 'bind_rsim'):
            players[a].bind_rsim(m)
        players[a].start(MatchContext(seat=a, seed=seed, own_order=tuple(m.decks[a]),
                                      command_delay=delay, opponent_delay=delay))
    channels = {a: CommandQueue(delay, capacity) for a in (0, 1)}
    waits, available_at = {0: 0, 1: 0}, {0: 0, 1: 0}
    command_hash = hashlib.sha256()
    play_log = {0: [], 1: []}
    reasons = {0: {}, 1: {}}
    timing = {a: dict(decisions=0, wall=0., cpu=0., overrun_ticks=0) for a in (0, 1)}
    cpu0_match = time.process_time()
    try:
        while not m.state['game_over'] and m.tick < max_ticks:
            tick = m.tick
            due = []
            for actor in (0, 1):
                ch = channels[actor]
                if ch.ready(tick):
                    c = ch.pending[0]
                    if m.hand_card(actor, c.action//576) != c.card:
                        raise AssertionError('pending slot changed')
                    due.append((actor, c.action, c.card))
            if due:
                for (actor, action, card), (ok, reason) in zip(due, m.execute(due)):
                    command_hash.update(f'{tick},{actor},{action},{int(bool(ok))};'.encode())
                    play_log[actor].append((tick, card, action, bool(ok)))
                    name = rs.DEPLOY_REASONS[reason]
                    reasons[actor][name] = reasons[actor].get(name, 0) + 1
                    channels[actor].finish(ok)
                if any(channels[a].ready(tick) for a in (0, 1)):
                    raise AssertionError('capacity 1: one command per seat per tick')
            if tick >= START_TICK and tick % POLICY_INTERVAL == 0 and not m.state['game_over']:
                for actor in (0, 1):
                    ch, player = channels[actor], players[actor]
                    with WINDOW:
                        wall0, cpu0 = time.monotonic(), time.process_time()
                        info = m.information(actor)
                        reserved = ch.own_packet(info, R.builder)
                        can_act = ch.available and tick >= waits[actor] and tick >= available_at[actor]
                        view = PublicView(tick, actor, info, reserved, m.public_events, tuple(ch.pending), can_act)
                        decision = player.act(view)
                        if not can_act:
                            ch.blocked += 1
                            continue
                        if decision.action < WAIT:
                            ch.submit(info, int(decision.action), R.costs, R.builder)
                        if decision.wait_ticks:
                            waits[actor] = tick + decision.wait_ticks
                        elapsed = time.monotonic()-wall0
                        if decision.stats is not None:
                            t = timing[actor]
                            t['decisions'] += 1; t['wall'] += elapsed; t['cpu'] += time.process_time()-cpu0
                            if player.deadline_seconds is not None:
                                _, late = apply_lateness(ch, waits, available_at, actor, tick,
                                                         elapsed, player.deadline_seconds)
                                t['overrun_ticks'] += late
            # Advance to the next event: the next poll tick or the next due command.
            nxt = max(START_TICK, (tick//POLICY_INTERVAL+1)*POLICY_INTERVAL)
            for ch in channels.values():
                if ch.pending:
                    nxt = min(nxt, max(tick+1, ch.pending[0].due))
            m.b.step([], min(nxt, max_ticks)-tick)
            m.refresh()
    finally:
        for player in players.values():
            player.close()
    s = m.state
    winner = s['winner'] if s['winner'] in (0, 1) else None
    result = dict(engine=f'royalesim-{rs_version()}', client=client, seed=seed, decks=m.decks,
                  players={a: players[a].name for a in (0, 1)},
                  terminal=bool(s['game_over']), winner=winner, draw=s['winner'] == 2, ticks=s['tick'],
                  crowns={a: s['players'][a]['crowns'] for a in (0, 1)},
                  towers={a: s['players'][a]['tower_hp'] for a in (0, 1)},
                  command_sha256=command_hash.hexdigest(), state_hash=m.b.state_hash(),
                  plays={a: len(play_log[a]) for a in (0, 1)},
                  accepted={a: sum(p[3] for p in play_log[a]) for a in (0, 1)},
                  deploy_reasons=reasons,
                  channels={a: channels[a].diagnostics() for a in (0, 1)},
                  translator=dict(m.tr.stats), own_cycle={a: dict(m.own[a].mismatch) for a in (0, 1)},
                  timing=timing, cpu_seconds=time.process_time()-cpu0_match)
    if verbose:
        result['play_log'] = play_log
    return result


def rs_version():
    from importlib.metadata import version
    return version('royalesim')
