"""A completed activation phase must not arm another shot next frame."""

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Projectile


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize(
    ("activation_delay", "first_hit_delay", "expected_shots"),
    [(3.3, 0.7, [80, 100]), (0.0, 0.05000000000000307, [1, 21])],
    ids=["full_activation", "captured_remainder"],
)
def test_king_activation_fires_once_then_uses_normal_interval(
    fast_path, activation_delay, first_hit_delay, expected_shots
):
    battle = BattleState(fast_path=fast_path)
    king = next(e for e in battle.entities.values()
                if e.player_id == 0 and e.card_stats.name == "KingTower")
    battle._spawn_unit_at_position(
        Position(6.381, 3.978), 1, battle.card_loader.get_card("HogRider"),
        deploy_delay_override=0, snap_to_valid=False,
    )
    king.activate()
    assert king.activation_delay_remaining == pytest.approx(3.3)
    assert king.activation_first_hit_delay_remaining == pytest.approx(0.7)
    king.activation_delay_remaining = activation_delay
    king.activation_first_hit_delay_remaining = first_hit_delay
    shots = []
    # The stationary target isolates the activation clock. Native neighbor
    # branch launches at2947 then2967; there is no extra shot at2948.
    for tick in range(1, expected_shots[-1] + 2):
        before = set(battle.entities)
        king.update_combat_component(battle.dt, battle)
        for identity in set(battle.entities) - before:
            if isinstance(battle.entities[identity], Projectile):
                shots.append(tick)
                assert king.activation_first_hit_delay_remaining == 0.0
    assert shots == expected_shots


@pytest.mark.parametrize("fast_path", [False, True])
def test_activation_without_target_does_not_bank_instant_first_shot(fast_path):
    # Native expanded reversed seed1305003: King first acquires Giant2949,
    # starts timeline550, then launches2958. Activation had already finished.
    battle = BattleState(fast_path=fast_path)
    king = next(e for e in battle.entities.values()
                if e.player_id == 0 and e.card_stats.name == "KingTower")
    king.activate()
    for _ in range(100):
        king.update_combat_component(battle.dt, battle)
    assert king.activation_first_hit_delay_remaining == 0
    assert king.target_id is None
    battle._spawn_unit_at_position(
        Position(6.381, 3.978), 1, battle.card_loader.get_card("HogRider"),
        deploy_delay_override=0, snap_to_valid=False,
    )
    shots = []
    for tick in range(1, 32):
        before = set(battle.entities)
        king.update_combat_component(battle.dt, battle)
        if any(isinstance(battle.entities[i], Projectile) for i in set(battle.entities) - before):
            shots.append(tick)
    assert shots == [10, 30]
