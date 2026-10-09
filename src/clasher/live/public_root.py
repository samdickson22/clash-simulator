"""Guard the public model's player ABI before entering native scripts."""
from dataclasses import dataclass, replace


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
            if info.packet.observation.terminal:
                raise ValueError('Cannot reconstruct a live root from a public match result')
            own = player_model(info.own, self.config['cards'])
            other = player_model(opponent, self.config['cards'])
            return super().root(replace(info, own=own), other, rng)
    return PublicResources


@dataclass(frozen=True)
class PublicMatchResult:
    """Result-screen observation supplied by the public capture/runtime owner.

    Crowns are (opponent, own). A terminal result need not be three crowns;
    only a three-crown winner establishes destruction of the other King.
    Native ended/receipt fields must never be passed through this interface.
    """
    episode_id: str
    timestamp_ms: int
    crowns: tuple[int, int]
    confidence: float

    def __post_init__(self):
        import math
        if type(self.timestamp_ms) is not int or self.timestamp_ms < 0:
            raise ValueError('Invalid result timestamp')
        if not isinstance(self.crowns, tuple) or len(self.crowns) != 2 or any(type(c) is not int or not 0 <= c <= 3 for c in self.crowns) or self.crowns == (3,3):
            raise ValueError('Invalid public result crowns')
        if not math.isfinite(self.confidence) or not 0 < self.confidence <= 1:
            raise ValueError('Invalid public result confidence')


def apply_match_result(public, result):
    """Join a public result to six slots; a missing King crop proves nothing."""
    from .tower_channel import TowerObservation, SLOT_NAMES
    if not isinstance(result, PublicMatchResult) or result.episode_id != public.episode_id or result.timestamp_ms > public.timestamp_ms:
        raise ValueError('Noncausal public match result')
    observations = {o.slot:o for o in public.tower_observations}
    for s,slot in enumerate(SLOT_NAMES):
        if s%3 == 0 and result.crowns[1-s//3] == 3:
            observations[slot] = TowerObservation(slot,'destroyed',confidence=result.confidence,
                last_observed_ms=result.timestamp_ms,destruction_evidence='public_match_result',match_ended=True)
        else:
            # Result overlays end current arena measurements. Preserve history
            # through PublicTowerModel, rather than treating overlays as rubble.
            old = observations.get(slot)
            observations[slot] = (TowerObservation(slot,confidence=result.confidence,last_observed_ms=result.timestamp_ms,match_ended=True) if s%3 == 0 else TowerObservation(slot,last_observed_ms=old.last_observed_ms if old else None))
    return replace(public,tower_observations=tuple(observations[s] for s in SLOT_NAMES))
