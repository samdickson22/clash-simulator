from __future__ import annotations

from clasher import battle as battle_module
from clasher.arena import Position
from clasher.battle import BattleState


def test_local_dense_bucket_bindings_preserve_exact_candidates() -> None:
    battle = BattleState(fast_path=True)
    for player_id, card_name, position in (
        (0, "Knight", Position(3.5, 10.5)),
        (0, "Musketeer", Position(9.5, 12.5)),
        (1, "Giant", Position(14.5, 20.5)),
    ):
        card = battle.card_loader.get_card(card_name)
        assert card is not None
        battle._spawn_unit_at_position(position, player_id, card)
    battle._refresh_fast_path_caches()

    for position in (
        Position(0.0, 0.0),
        Position(3.5, 10.5),
        Position(9.0, 16.0),
        Position(17.999, 31.999),
    ):
        for radius in (0.0, 0.5, 2.0, 7.5, 31.999):
            battle_module._USE_LOCAL_DENSE_BUCKET_BINDINGS = False
            reference = battle.iter_entities_in_radius(position, radius)
            battle_module._USE_LOCAL_DENSE_BUCKET_BINDINGS = True
            candidate = battle.iter_entities_in_radius(position, radius)

            assert candidate == reference
            assert candidate is not reference
