"""Guard the public model's player ABI before entering native scripts."""
from dataclasses import replace


def player_model(player, cards):
    # HUD can report its explicit empty class. Preserve slot order, and never
    # let a non-card sentinel become a native metadata lookup.
    hand = [None if card in (None, '', 'empty') else card for card in player['hand']]
    cycle = list(player['cycle'])
    if any(card not in cards for card in [c for c in hand if c is not None]+cycle):
        raise ValueError('Public player model contains a card outside native scope')
    return dict(player, hand=hand, cycle=cycle)


def public_resources(base):
    class PublicResources(base):
        def root(self, info, opponent, rng):
            own = player_model(info.own, self.config['cards'])
            other = player_model(opponent, self.config['cards'])
            return super().root(replace(info, own=own), other, rng)
    return PublicResources
