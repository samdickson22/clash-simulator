from __future__ import annotations

from clasher import entities as entities_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.factory.dynamic_factory import building_from_values


def _building(
    entity_id: int,
    *,
    name: str,
    player_id: int,
    y: float,
    attack_range: float,
    sight_range: float,
) -> Building:
    stats = building_from_values(
        name=name,
        hitpoints=1200,
        damage=80,
        range_tiles=attack_range,
        sight_range_tiles=sight_range,
        hit_speed_ms=1000,
        deploy_time_ms=0,
        collision_radius_tiles=1.0,
        lifetime_ms=None,
        target_type="TID_TARGETS_AIR_AND_GROUND",
    )
    return Building(
        id=entity_id,
        position=Position(9.0, y),
        player_id=player_id,
        card_stats=stats,
        hitpoints=1200,
        max_hitpoints=1200,
        damage=80,
        range=attack_range,
        sight_range=sight_range,
        attack_cooldown=10.0,
    )


def _run_acquisition(
    monkeypatch,
    *,
    bounded: bool,
    attack_range: float,
    sight_range: float,
    target_distance: float,
) -> tuple[tuple[int | None, float, float], bool]:
    battle = BattleState(fast_path=False)
    attacker = _building(
        1,
        name="TestDefense",
        player_id=0,
        y=10.0,
        attack_range=attack_range,
        sight_range=sight_range,
    )
    crown = _building(
        2,
        name="Tower",
        player_id=1,
        y=10.0 + target_distance,
        attack_range=7.0,
        sight_range=7.0,
    )
    attacker.battle_state = battle
    crown.battle_state = battle
    battle.entities = {attacker.id: attacker, crown.id: crown}
    battle._alive_buildings = [attacker, crown]

    fallback_values: list[bool] = []
    original_selector = Building.get_nearest_target

    def record_selector(self, entities, **kwargs):
        fallback_values.append(bool(kwargs.get("include_crown_fallback", True)))
        return original_selector(self, entities, **kwargs)

    monkeypatch.setattr(
        entities_module,
        "_USE_RANGE_BOUNDED_BUILDING_CROWN_FALLBACK",
        bounded,
    )
    monkeypatch.setattr(Building, "get_nearest_target", record_selector)
    attacker._update_active_combat(battle.dt, battle)
    state = (attacker.target_id, attacker.attack_cooldown, crown.hitpoints)
    return state, fallback_values[-1]


def test_bounded_building_skips_only_unreachable_crown_fallback(monkeypatch) -> None:
    with monkeypatch.context() as reference_patch:
        reference_state, reference_fallback = _run_acquisition(
            reference_patch,
            bounded=False,
            attack_range=6.0,
            sight_range=6.0,
            target_distance=10.0,
        )
    with monkeypatch.context() as candidate_patch:
        candidate_state, candidate_fallback = _run_acquisition(
            candidate_patch,
            bounded=True,
            attack_range=6.0,
            sight_range=6.0,
            target_distance=10.0,
        )

    assert candidate_state == reference_state
    assert reference_fallback is True
    assert candidate_fallback is False


def test_bounded_building_retains_required_long_range_fallback(monkeypatch) -> None:
    with monkeypatch.context() as reference_patch:
        reference_state, reference_fallback = _run_acquisition(
            reference_patch,
            bounded=False,
            attack_range=10.0,
            sight_range=6.0,
            target_distance=9.5,
        )
    with monkeypatch.context() as candidate_patch:
        candidate_state, candidate_fallback = _run_acquisition(
            candidate_patch,
            bounded=True,
            attack_range=10.0,
            sight_range=6.0,
            target_distance=9.5,
        )

    assert candidate_state == reference_state
    assert candidate_state[0] == 2
    assert reference_fallback is candidate_fallback is True
