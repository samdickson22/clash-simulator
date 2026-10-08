"""Serving D1 from accepted public events and the player's own opening order.

No BattleState or opponent deck is accepted by this adapter. Row schema and
rounding match SidecarObserver; tests compare independent observer output bytes.
"""
import numpy as np
from .paths import setup
setup()
from derived_d1 import DerivedD1, PublicEvent
from own_cycle import OwnCycle


class D1Tracker:
    def __init__(self, builder, costs, seat, own_order):
        self.builder, self.seat = builder, seat
        self.trackers = [DerivedD1(costs), DerivedD1(costs)]
        self.own = OwnCycle(own_order)
        self.offset = 0
        self.last_tick = 0

    def token(self, name):
        if name is None:
            return 0
        token = self.builder.token_id(name, namespace='card_action')
        if token <= 1:
            raise ValueError(f'unknown public card: {name}')
        return token

    def update(self, tick, events):
        if tick < self.last_tick or len(events) < self.offset:
            raise ValueError('public stream moved backwards')
        for row in events[self.offset:]:
            e = PublicEvent(**{k: row[k] for k in PublicEvent.__dataclass_fields__})
            if e.tick > tick:
                raise ValueError('future public event')
            seat = row['seat']
            self.trackers[seat].accept(e)
            if seat == self.seat and e.kind == 'card':
                self.own.play(e.tick, e.name)
        self.offset = len(events)
        self.last_tick = tick
        for tracker in self.trackers:
            tracker.advance(tick)
        self.own.advance(tick)
        return self.row(tick)

    def history(self, tracker, tick):
        ids = np.zeros(8, np.int16)
        features = np.zeros((8, 3), np.float32)
        for i, e in enumerate(reversed(tracker.plays)):
            x, y = (18-e.x, 32-e.y) if self.seat else (e.x, e.y)
            ids[i] = self.token(e.name)
            features[i] = [min(1., (tick-e.tick)/1200), x/18, y/32]
        return ids, features

    def row(self, tick):
        d = self.trackers[1-self.seat].derived()
        opp_ids, opp_features = self.history(self.trackers[1-self.seat], tick)
        own_ids, own_features = self.history(self.trackers[self.seat], tick)
        ability_ids = np.zeros(8, np.int16)
        ability_ages = np.zeros(8, np.float32)
        for i, e in enumerate(reversed(self.trackers[1-self.seat].abilities)):
            ability_ids[i] = self.token(e.name)
            ability_ages[i] = min(1., (tick-e.tick)/1200)
        tokens = lambda ns: np.array([self.token(n) for n in ns], np.int16)
        return dict(opp_elixir=np.float32(d['elixir']), opp_elixir_units=np.int32(d['elixir_units']),
                    opp_hand_known=tokens(d['hand_known']), opp_next_card=np.int16(self.token(d['next_card'])),
                    opp_queue=tokens(d['cycle_positions'][:4]),
                    opp_queue_known=np.array(d['cycle_positions_known'][:4], np.bool_),
                    opp_queue_len=np.int8(len(d['cycle_positions'])),
                    opp_refill_remaining=np.int16(d['refill']), opp_cards_revealed=np.int8(d['cards_revealed']),
                    elixir_exact=np.bool_(True), own_deck=tokens(self.own.deck),
                    own_queue=tokens(list(self.own.queue)[:4]), own_queue_len=np.int8(len(self.own.queue)),
                    own_refill_remaining=np.int16(self.own.refill),
                    opp_recent_play_ids=opp_ids, opp_recent_play_features=opp_features,
                    own_recent_play_ids=own_ids, own_recent_play_features=own_features,
                    opp_ability_ids=ability_ids, opp_ability_ages=ability_ages)


def model_packet(packet, mask):
    from clasher.rl.contract_v5 import champion_button_flags
    obs = packet.observation
    keys = ('hand_ids', 'hand_levels', 'global_features', 'entity_ids', 'entity_levels',
            'entity_features', 'entity_mask', 'opponent_seen_card_ids')
    return {**{key: getattr(obs, key) for key in keys},
            'champion_button': bool(champion_button_flags(packet.global_feature_confidence)), 'action_mask': mask}
