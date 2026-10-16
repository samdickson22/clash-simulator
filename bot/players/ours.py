"""Play one match in our engine (Python physics) with two bot.players Players.

Game loop = reports/explore/x4s/run.py:79-282 with the seat-specific arms replaced by
the uniform Player interface. Kept verbatim: battle construction and deck shuffle,
PublicRecorder events, per-seat CommandQueue(27, capacity 1) delayed execution with
reservation, 5-tick polling from tick 90 (search only on 10-tick multiples), timed
waits, abilities disabled, honest lateness for players that declare a wall deadline,
GC deferral during decisions, and the command hash.
"""
from __future__ import annotations

import hashlib
import random
import time

from .base import MatchContext, PublicView, POLICY_INTERVAL, START_TICK, WAIT


def x4s_setup(rt, index, base=4503604807370496):
    """Seed, seat and decks of X4S reporting index i (x4s/run.py:97-100, 313-314).

    The bot under test sits in `seat`; its deck is X-deck i%5, the opponent's
    (i//5)%5; one Random(seed) shuffles own then other. Default base = X4S
    reporting bank; use a fresh bank for new reporting (see INVENTORY.md).
    """
    selected = rt.x4s_decks()
    seed, seat = base+index, index % 2
    own, other = list(selected[index % 5]), list(selected[(index//5) % 5])
    rng = random.Random(seed)
    rng.shuffle(own); rng.shuffle(other)
    return dict(seed=seed, seat=seat, decks=[own, other] if seat == 0 else [other, own])


def play_match(rt, players, *, seed, decks, max_ticks=6001, delay=27, capacity=1, verbose=False):
    """players: {0: Player, 1: Player}; decks: [deck_seat0, deck_seat1], already in
    initial order (deck[:4] = hand, rest = cycle queue). Use x4s_setup for X4S cases."""
    from fair_player import observe
    from stage2_matches import battle
    from derived_public_state import PublicEvent
    from imitation.evaluation.events import PublicRecorder
    from clasher.rl.action_space import DiscreteTileActionSpace
    from clasher.analysis.loss_review.delay_fixes import CommandQueue
    from latency import apply_lateness
    from gc_window import WINDOW
    R = rt.R
    decks = [list(d) for d in decks]
    b = battle(dict(seed=seed, decks=decks), R.builder.loader)
    for a in (0, 1):
        players[a].start(MatchContext(seat=a, seed=seed, own_order=tuple(
            list(b.players[a].hand)+list(b.players[a].cycle_queue)), command_delay=delay,
            opponent_delay=delay))
    # Optional per-seat perception alias (bot/fullpool/alias.py AliasedPlayer); None for every other player.
    aliases = {a: getattr(players[a], 'observe_alias', None) for a in (0, 1)}
    space = DiscreteTileActionSpace()
    recorder = PublicRecorder(R.builder)
    recorder.__enter__(); recorder.bind(b)
    channels = {a: CommandQueue(delay, capacity) for a in (0, 1)}
    waits, available_at = {0: 0, 1: 0}, {0: 0, 1: 0}
    public_events = {0: [], 1: []}
    command_hash = hashlib.sha256()
    plays = {0: [], 1: []}
    timing = {a: dict(decisions=0, wall=0., cpu=0., overrun_ticks=0) for a in (0, 1)}
    cpu0_match = time.process_time()

    def execute(actor, command):
        if b.players[actor].hand[command.action//576] != command.card:
            raise AssertionError('pending slot changed')
        ok = space.apply_action(b, actor, command.action)
        command_hash.update(f'{b.tick},{actor},{command.action},{int(bool(ok))};'.encode())
        plays[actor].append((b.tick, command.card, command.action, bool(ok)))
        if ok:
            public_events[1-actor].append(PublicEvent(b.tick, 'card', command.card))
        return ok

    try:
        while not b.game_over and b.tick < max_ticks:
            for actor in (0, 1):
                ch = channels[actor]
                while ch.ready(b.tick):
                    ch.finish(execute(actor, ch.pending[0]))
            if b.tick >= START_TICK and b.tick % POLICY_INTERVAL == 0:
                for actor in (0, 1):
                    ch, player = channels[actor], players[actor]
                    with WINDOW:
                        wall0, cpu0 = time.monotonic(), time.process_time()
                        info = observe(b, R.builder, actor, public_events[actor])
                        if aliases[actor] is not None:
                            info = aliases[actor].info(info)
                        reserved = ch.own_packet(info, R.builder)
                        can_act = ch.available and b.tick >= waits[actor] and b.tick >= available_at[actor]
                        view = PublicView(b.tick, actor, info, reserved,
                                          recorder.public_events if aliases[actor] is None
                                          else aliases[actor].recorder(recorder.public_events),
                                          tuple(ch.pending), can_act)
                        decision = player.act(view)
                        if not can_act:
                            ch.blocked += 1
                            continue
                        if decision.action < WAIT:
                            ch.submit(info, int(decision.action), R.costs, R.builder)
                        if decision.wait_ticks:
                            waits[actor] = b.tick + decision.wait_ticks
                        elapsed = time.monotonic()-wall0
                        if decision.stats is not None:
                            t = timing[actor]
                            t['decisions'] += 1; t['wall'] += elapsed; t['cpu'] += time.process_time()-cpu0
                            if player.deadline_seconds is not None:
                                _, late = apply_lateness(ch, waits, available_at, actor, b.tick,
                                                         elapsed, player.deadline_seconds)
                                t['overrun_ticks'] += late
            b.step()
    finally:
        for player in players.values():
            player.close()
        recorder.__exit__(None, None, None)
    winner = b.winner if b.game_over else None
    towers = {a: [round(float(getattr(b.players[a], k)), 1) for k in
                  ('king_tower_hp', 'left_tower_hp', 'right_tower_hp')] for a in (0, 1)}
    result = dict(seed=seed, decks=decks, players={a: players[a].name for a in (0, 1)},
                  terminal=bool(b.game_over), winner=winner, ticks=b.tick,
                  towers=towers,
                  command_sha256=command_hash.hexdigest(),
                  plays={a: len(plays[a]) for a in (0, 1)},
                  accepted={a: sum(p[3] for p in plays[a]) for a in (0, 1)},
                  channels={a: channels[a].diagnostics() for a in (0, 1)},
                  timing=timing, cpu_seconds=time.process_time()-cpu0_match)
    if verbose:
        result['play_log'] = plays
    return result
