"""Use the sealed gate(c) adapter verbatim; delayed command control lives outside."""
from imitation.evaluation.standalone import StandalonePlayer
from imitation.evaluation.d1 import model_packet


class V1Policy:
    def __init__(self, policy, builder, costs, seat, own_order, seed):
        self.player = StandalonePlayer(policy, builder, costs, seat, own_order, seed)
        self.action = 2304
        self.mask = None
        self.polls = 0

    def poll(self, tick, packet, public_events):
        self.action, self.mask = self.player.decide(tick, packet, public_events)
        self.polls += 1
        return self.action

    @property
    def opponent_elixir(self):
        return float(self.player.last_d1['opp_elixir'])
