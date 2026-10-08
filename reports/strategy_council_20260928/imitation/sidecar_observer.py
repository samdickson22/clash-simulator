"""Non-mutating public event/row observer for the frozen v5 reconstruction.

Hooks call the original methods exactly once. Hidden truth and extractor top-up
counters are emitted only to audit arrays, never supplied to DerivedD1.
Use one observer per process at a time, as a context manager.
"""
from collections import Counter
import sys
import numpy as np
from derived_d1 import DerivedD1, PublicEvent
from own_cycle import OwnCycle


class SidecarObserver:
    def __init__(self, builder):
        self.builder = builder
        self.battle = None
        self.rows = []
        self.audit = []
        self.position = None
        self.public_events = []

    def token(self, name):
        if name is None: return 0
        token = self.builder.token_id(name, namespace='card_action')
        if token <= 1: raise ValueError(f'unknown public card token {name}')
        return token

    def __enter__(self):
        from clasher.battle import BattleState
        from clasher.player import PlayerState
        from clasher.cards.elixir_collector import ElixirProduction
        from clasher.mechanics.champion.ability import ActiveAbility
        originals = (BattleState.deploy_card, PlayerState.play_card, ElixirProduction._give, ActiveAbility.activate)
        self.restore = (BattleState, PlayerState, ElixirProduction, ActiveAbility, originals)

        def deploy(b, seat, name, position):
            previous = self.position
            self.position = (position.x, position.y)
            try: return originals[0](b, seat, name, position)
            finally: self.position = previous

        def card(player, name, stats):
            ok = originals[1](player, name, stats)
            if ok and self.battle is not None and id(player) in self.seats:
                seat = self.seats[id(player)]
                x, y = self.position
                self.event(seat, PublicEvent(self.battle.tick, 'card', name, 0., x, y))
            return ok

        def grant(entity, amount):
            if entity.battle_state is self.battle and amount > 0 and not self.battle.game_over:
                self.event(entity.player_id, PublicEvent(self.battle.tick, 'collector', 'Elixir Collector', amount))
            return originals[2](entity, amount)

        def ability(ability, entity, b):
            amount = float(ability.elixir_cost)
            ok = originals[3](ability, entity, b)
            if ok and b is self.battle:
                name = entity.card_stats.name
                if name == 'Goblinstein_doctor': name = 'Goblinstein'
                self.event(entity.player_id, PublicEvent(b.tick, 'ability', name, amount))
            return ok

        BattleState.deploy_card = deploy
        PlayerState.play_card = card
        ElixirProduction._give = staticmethod(grant)
        ActiveAbility.activate = ability
        return self

    def __exit__(self, *_):
        battle, player, collector, ability, old = self.restore
        battle.deploy_card, player.play_card = old[:2]
        collector._give = staticmethod(old[2])
        ability.activate = old[3]

    def event(self, seat, event):
        self.trackers[seat].accept(event)
        if seat == self.learner and event.kind == 'card':
            self.own.play(event.tick, event.name)
        self.public_events.append(dict(seat=seat, **event.__dict__))

    def history(self, tracker, tick):
        ids = np.zeros(8, np.int16)
        features = np.zeros((8, 3), np.float32)
        for i, e in enumerate(reversed(tracker.plays)):
            x, y = (18-e.x, 32-e.y) if self.learner else (e.x, e.y)
            ids[i] = self.token(e.name)
            features[i] = [min(1., (tick-e.tick)/1200), x/18, y/32]
        return ids, features

    def __call__(self, battle, learner, label):
        if self.battle is None:
            assert battle.tick == 0
            self.battle, self.learner = battle, learner
            self.seats = {id(p):s for s,p in enumerate(battle.players)}
            # Costs are a public catalog, NOT identities from the hidden deck.
            from clasher.data import CardDataLoader
            definitions = battle.card_loader.load_card_definitions()
            costs = {n:float(battle.card_loader.get_card(n).mana_cost) for n in definitions
                     if battle.card_loader.get_card(n).mana_cost is not None}
            self.trackers = [DerivedD1(costs), DerivedD1(costs)]
            p = battle.players[learner]
            self.own = OwnCycle(list(p.hand) + list(p.cycle_queue))
        tick = battle.tick
        for tracker in self.trackers: tracker.advance(tick)
        self.own.advance(tick)
        d = self.trackers[1-learner].derived()
        opp_ids, opp_features = self.history(self.trackers[1-learner], tick)
        own_ids, own_features = self.history(self.trackers[learner], tick)
        ability_ids = np.zeros(8, np.int16); ability_ages = np.zeros(8, np.float32)
        for i,e in enumerate(reversed(self.trackers[1-learner].abilities)):
            ability_ids[i] = self.token(e.name); ability_ages[i] = min(1., (tick-e.tick)/1200)
        row = dict(opp_elixir=np.float32(d['elixir']), opp_elixir_units=np.int32(d['elixir_units']),
                   opp_hand_known=np.array([self.token(n) for n in d['hand_known']], np.int16),
                   opp_next_card=np.int16(self.token(d['next_card'])),
                   opp_queue=np.array([self.token(n) for n in d['cycle_positions'][:4]], np.int16),
                   opp_queue_known=np.array(d['cycle_positions_known'][:4], np.bool_),
                   opp_queue_len=np.int8(len(d['cycle_positions'])),
                   opp_refill_remaining=np.int16(d['refill']),
                   opp_cards_revealed=np.int8(d['cards_revealed']), elixir_exact=np.bool_(True),
                   own_deck=np.array([self.token(n) for n in self.own.deck], np.int16),
                   own_queue=np.array([self.token(n) for n in list(self.own.queue)[:4]], np.int16),
                   own_queue_len=np.int8(len(self.own.queue)), own_refill_remaining=np.int16(self.own.refill),
                   opp_recent_play_ids=opp_ids, opp_recent_play_features=opp_features,
                   own_recent_play_ids=own_ids, own_recent_play_features=own_features,
                   opp_ability_ids=ability_ids, opp_ability_ages=ability_ages)
        self.rows.append(row)
        # Deliberately separate truth path. No hidden field above feeds D1.
        truth = battle.players[1-learner]
        caller_counters = sys._getframe(1).f_locals.get('counters')
        if caller_counters is not None:
            self.audit_counters = caller_counters
        topup = self.audit_counters['opponent_elixir_topup_total']
        hand = Counter(filter(None, truth.hand))
        hand_bad = bool(Counter(filter(None, d['hand_known'])) - hand)
        queue_bad = any(n is not None and n != truth.cycle_queue[i]
                        for i,n in enumerate(d['cycle_positions']))
        own = battle.players[learner]
        own_bad = (self.own.hand != list(own.hand) or list(self.own.queue) != list(own.cycle_queue)
                   or self.own.refill != own.next_card_refill_cooldown_ms)
        error = abs(d['elixir'] - truth.elixir)
        self.audit.append(dict(opp_true_elixir=np.float64(truth.elixir),
            opp_topup_total=np.float64(topup), elixir_error=np.float64(error),
            opp_true_hand=np.array([self.token(n) for n in truth.hand], np.int16),
            opp_true_queue=np.array([self.token(n) for n in list(truth.cycle_queue)] + [0]*(8-len(truth.cycle_queue)), np.int16),
            violation=np.array([error > topup + 1e-9, hand_bad, queue_bad,
                               d['refill'] != truth.next_card_refill_cooldown_ms, own_bad], np.bool_)))

    def arrays(self):
        return ({k:np.asarray([r[k] for r in self.rows]) for k in self.rows[0]},
                {k:np.asarray([r[k] for r in self.audit]) for k in self.audit[0]})


def intent_targets(compact, sidecar, cut_tick):
    """Future labels only; right-censor at cut. Never consumed as inputs."""
    actions = compact['expert_actions']; ticks = compact['submitted_ticks']
    valid = compact['expert_action_supervision_valid']
    n = len(actions)
    card = np.zeros(n, np.int16); delay = np.zeros(n, np.int32)
    censored = np.ones(n, np.bool_); index = np.full(n, -1, np.int8)
    next_row = None
    for i in range(n-1, -1, -1):
        if valid[i] and actions[i] < 2304: next_row = i
        if next_row is None:
            delay[i] = max(0, cut_tick-int(ticks[i]))
        else:
            token = compact['hand_ids'][next_row, actions[next_row]//576]
            card[i] = token
            delay[i] = int(ticks[next_row])-int(ticks[i])
            index[i] = list(sidecar['own_deck'][i]).index(token)
            censored[i] = False
    # Twelve boundaries (0.05 ... 10 seconds), followed by the tail bin.
    edges = np.geomspace(.05, 10., 12)
    return dict(intent_card=card, intent_deck_index=index, intent_delay_ticks=delay,
                intent_bin=np.searchsorted(edges, delay/20, side='left').astype(np.int8),
                intent_censored=censored)
