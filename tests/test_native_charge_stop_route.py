"""A charged hit stops movement and discards the old route."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("card", ["DarkPrince", "Prince"])
def test_immediate_charge_hit_clears_route(fast_path, card):
    # Native expanded seed1305001: Dark Prince stops at811 to strike a newly
    # deployed Ice Golem. Route is empty at813 and before resuming at922.
    battle = BattleState(fast_path=fast_path)
    for name, owner, xy in (
        (card, 0, (14.739, 22.454)),
        ("IceGolem", 1, (14.5, 22.5)),
    ):
        battle._spawn_unit_at_position(
            Position(*xy), owner, battle.card_loader.get_card(name),
            deploy_delay_override=0, snap_to_valid=False,
        )
    attacker, target = list(battle.entities.values())[-2:]
    attacker._native_natural_movement_active = True
    attacker._native_ground_route_cells = [(29, 47)]
    attacker._ground_path_cache_key = ((29, 47), (), 1, False)
    attacker._native_charge_progress = 10000
    attacker.is_charging = True
    attacker.attack_cooldown = 0
    hp = target.hitpoints

    battle.step()

    assert target.hitpoints < hp
    assert not attacker._native_natural_movement_active
    assert attacker._native_ground_route_cells == []
    assert attacker._ground_path_cache_key is None


@pytest.mark.parametrize("fast_path", [False, True])
def test_attack_after_stun_discards_retained_walking_route(fast_path):
    # Native family028: route retained at2951, cleared when attacking at2952.
    battle = BattleState(fast_path=fast_path)
    for name, owner, xy in (
        ("Archers", 0, (2.791, 12.797)),
        ("Skeletons", 1, (3.771, 15.594)),
    ):
        battle._spawn_unit_at_position(
            Position(*xy), owner, battle.card_loader.get_card(name),
            deploy_delay_override=0, snap_to_valid=False,
        )
    attacker = next(e for e in battle.entities.values() if e.card_stats and e.card_stats.name == "Archer" and e.player_id == 0)
    attacker._native_natural_movement_active = False
    attacker._native_ground_route_cells = [(6, 28), (6, 29), (7, 30)]
    attacker._ground_path_cache_key = ((12, 48), (), 1, False)
    attacker.apply_stun(.05)
    battle.step()
    assert attacker._native_ground_route_cells
    battle.step()
    assert attacker.target_id is not None
    assert not attacker._native_natural_movement_active
    assert attacker._native_ground_route_cells == []
    assert attacker._ground_path_cache_key is None
