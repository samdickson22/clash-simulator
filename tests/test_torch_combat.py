from __future__ import annotations

import random
from collections.abc import Sequence

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.entities import Building, Entity, TargetType, Troop
from clasher.factory.dynamic_factory import building_from_values, troop_from_values
from clasher.kinematics import tiles_to_logic_units
from clasher.torch_sim.combat import (
    StationaryCombatState,
    UnsupportedStationaryCombatError,
    projectile_lethal_reservations,
    select_stationary_targets,
    stationary_combat_support_mask,
    step_stationary_combat_,
)
from clasher.unit_traits import is_airborne_target, is_native_building_target


def _troop(
    entity_id: int,
    player_id: int,
    x: float,
    y: float,
    *,
    damage: int = 80,
    hp: int = 500,
    attack_range: float = 1.0,
    sight: float = 5.5,
    attacks_air: bool = False,
    buildings_only: bool = False,
    cooldown: float = 10.0,
) -> Troop:
    target_type = (
        "TID_TARGETS_BUILDINGS"
        if buildings_only
        else "TID_TARGETS_AIR_AND_GROUND"
        if attacks_air
        else "TID_TARGETS_GROUND"
    )
    stats = troop_from_values(
        name=f"TensorTestTroop{entity_id}",
        hitpoints=hp,
        damage=damage,
        speed_logic_units_per_tick=0.0,
        range_tiles=attack_range,
        sight_range_tiles=sight,
        hit_speed_ms=1_000,
        collision_radius_tiles=0.5,
        deploy_time_ms=0,
        load_time_ms=200,
        target_type=target_type,
        attacks_ground=True,
        attacks_air=attacks_air,
    )
    return Troop(
        id=entity_id,
        position=Position(x, y),
        player_id=player_id,
        card_stats=stats,
        hitpoints=float(hp),
        max_hitpoints=float(hp),
        damage=float(damage),
        range=attack_range,
        sight_range=sight,
        speed=0.0,
        target_type=TargetType.BOTH if attacks_air else TargetType.GROUND,
        attack_cooldown=cooldown,
    )


def _building(
    entity_id: int,
    player_id: int,
    x: float,
    y: float,
    *,
    hp: int = 700,
    damage: int = 0,
    attack_range: float = 0.0,
    sight: float = 0.0,
    cooldown: float = 10.0,
    name: str | None = None,
) -> Building:
    stats = building_from_values(
        name=name or f"TensorTestBuilding{entity_id}",
        hitpoints=hp,
        damage=damage,
        range_tiles=attack_range,
        sight_range_tiles=sight,
        hit_speed_ms=1_000,
        deploy_time_ms=0,
        collision_radius_tiles=1.0,
        lifetime_ms=None,
        target_type="TID_TARGETS_AIR_AND_GROUND",
    )
    return Building(
        id=entity_id,
        position=Position(x, y),
        player_id=player_id,
        card_stats=stats,
        hitpoints=float(hp),
        max_hitpoints=float(hp),
        damage=float(damage),
        range=attack_range,
        sight_range=sight,
        attack_cooldown=cooldown,
    )


def _enabled_entity(
    card_name: str,
    entity_id: int,
    player_id: int,
    x: float,
    y: float,
) -> Entity:
    stats = CardDataLoader().get_card(card_name)
    assert stats is not None
    hp = float(stats.scaled_hitpoints or stats.hitpoints or 100)
    damage = float(stats.scaled_damage or stats.damage or 0)
    common = {
        "id": entity_id,
        "position": Position(x, y),
        "player_id": player_id,
        "card_stats": stats,
        "hitpoints": hp,
        "max_hitpoints": hp,
        "damage": damage,
        "range": float(stats.range or 0.0),
        "sight_range": float(stats.sight_range or 0.0),
        "attack_cooldown": 10.0,
    }
    if str(stats.card_type).lower() == "building":
        return Building(**common)
    return Troop(
        **common,
        speed=float(stats.speed or 0.0),
        target_type=TargetType.BOTH,
        is_air_unit=bool(card_name == "Bats"),
    )


def _to_tensor_state(
    batches: Sequence[Sequence[Entity]],
    *,
    capacity: int | None = None,
    device: str | torch.device = "cpu",
) -> StationaryCombatState:
    capacity = capacity or max(len(entities) for entities in batches)
    state = StationaryCombatState.empty(len(batches), capacity, device=device)
    for batch_index, entities in enumerate(batches):
        id_to_slot = {entity.id: slot for slot, entity in enumerate(entities)}
        for slot, entity in enumerate(entities):
            state.present[batch_index, slot] = True
            state.entity_id[batch_index, slot] = entity.id
            state.encounter_order[batch_index, slot] = slot
            state.kind[batch_index, slot] = entity.entity_kind
            state.owner[batch_index, slot] = entity.player_id
            state.x_units[batch_index, slot] = tiles_to_logic_units(entity.position.x)
            state.y_units[batch_index, slot] = tiles_to_logic_units(entity.position.y)
            state.collision_radius_units[batch_index, slot] = tiles_to_logic_units(
                entity.get_collision_radius()
            )
            state.target_distance_discount_sq_units[batch_index, slot] = int(
                entity._native_target_distance_discount_sq_units
            )
            state.hp[batch_index, slot] = entity.hitpoints
            state.max_hp[batch_index, slot] = entity.max_hitpoints
            state.damage[batch_index, slot] = entity.damage
            state.alive[batch_index, slot] = entity.is_alive
            state.targetable[batch_index, slot] = not bool(
                getattr(entity, "_hidden_building", False)
            )
            state.airborne[batch_index, slot] = is_airborne_target(entity)
            state.building_target[batch_index, slot] = is_native_building_target(entity)
            crown_slot = getattr(entity, "_crown_tower_slot", None)
            state.crown_slot[batch_index, slot] = {
                None: -1,
                "left": 0,
                "right": 1,
                "king": 2,
            }[crown_slot]
            state.range_units[batch_index, slot] = tiles_to_logic_units(entity.range)
            state.sight_range_units[batch_index, slot] = tiles_to_logic_units(
                entity.sight_range
            )
            state.sight_clip_units[batch_index, slot] = tiles_to_logic_units(
                float(getattr(entity.card_stats, "sight_clip", 0.0) or 0.0)
            )
            state.sight_clip_side_units[batch_index, slot] = tiles_to_logic_units(
                float(getattr(entity.card_stats, "sight_clip_side", 0.0) or 0.0)
            )
            state.can_attack_air[batch_index, slot] = entity._can_attack_air()
            state.can_attack_ground[batch_index, slot] = entity._can_attack_ground()
            state.buildings_only[batch_index, slot] = bool(
                getattr(entity.card_stats, "targets_only_buildings", False)
            )
            state.uses_projectile[batch_index, slot] = entity._uses_projectiles()
            state.target_slot[batch_index, slot] = id_to_slot.get(entity.target_id, -1)
            state.deploy_remaining[batch_index, slot] = entity.deploy_delay_remaining
            state.stunned[batch_index, slot] = entity.is_stunned()
            state.forced_movement[batch_index, slot] = entity.forced_movement_active
            state.attack_cooldown[batch_index, slot] = entity.attack_cooldown
            state.hit_speed_ms[batch_index, slot] = int(
                entity.card_stats.hit_speed or 0
            )
            state.first_hit_ms[batch_index, slot] = int(
                entity.card_stats.first_hit_time or 0
            )
            state.attack_rate_multiplier[batch_index, slot] = (
                entity.get_attack_rate_multiplier()
            )
            state.attack_preload_blocked[batch_index, slot] = (
                entity._attack_preload_blocked
            )
            state.attack_windup_active[batch_index, slot] = entity._attack_windup_active
            state.started_projectile_hit_cycle[batch_index, slot] = (
                entity.has_started_projectile_hit_cycle()
            )
            state.area_radius_units[batch_index, slot] = tiles_to_logic_units(
                entity._attack_area_damage_radius()
            )
            state.self_as_aoe_center[batch_index, slot] = bool(
                getattr(entity.card_stats, "self_as_aoe_center", False)
            )
            state.last_attack_time[batch_index, slot] = entity.last_attack_time
            state.has_attacked_once[batch_index, slot] = bool(
                getattr(entity, "_has_attacked_once", False)
            )
    return state


def _attach_battle(entities: Sequence[Entity]) -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities = {entity.id: entity for entity in entities}
    for entity in entities:
        entity.battle_state = battle
    battle._alive_buildings = [
        entity for entity in entities if isinstance(entity, Building)
    ]
    return battle


@pytest.mark.parametrize("seed", range(10))
def test_randomized_crowded_target_selection_matches_scalar_oracle(seed: int) -> None:
    rng = random.Random(seed)
    attacker = _troop(
        1,
        0,
        9.0,
        12.0,
        sight=6.0,
        attacks_air=bool(seed % 2),
        buildings_only=bool(seed % 3 == 0),
    )
    targets: list[Entity] = []
    for index in range(30):
        x = (5_000 + rng.randrange(8_001)) / 1_000.0
        y = (8_000 + rng.randrange(8_001)) / 1_000.0
        entity_id = index + 2
        if rng.random() < 0.3:
            target = _building(entity_id, 1, x, y)
        else:
            target = _troop(entity_id, 1, x, y)
            target.is_air_unit = rng.random() < 0.3
        targets.append(target)
    rng.shuffle(targets)
    ordered = [attacker, *targets]
    oracle_entities = {entity.id: entity for entity in ordered}
    expected = attacker.get_nearest_target(oracle_entities)

    state = _to_tensor_state([ordered])
    selected, fallback = select_stationary_targets(
        state, torch.tensor([0], dtype=torch.int64)
    )
    actual = None if selected.item() < 0 else ordered[selected.item()]
    assert (None if expected is None else expected.id) == (
        None if actual is None else actual.id
    )
    assert not fallback.item()


def test_exact_tie_prefers_character_before_earlier_building_like_oracle() -> None:
    attacker = _troop(1, 0, 9.0, 10.0, sight=6.0)
    earlier_building = _building(2, 1, 9.0, 12.0)
    later_character = _troop(3, 1, 9.0, 12.0)
    ordered: list[Entity] = [attacker, earlier_building, later_character]
    expected = attacker.get_nearest_target({entity.id: entity for entity in ordered})
    state = _to_tensor_state([ordered])
    selected, _ = select_stationary_targets(state, torch.tensor([0], dtype=torch.int64))
    assert expected is later_character
    assert selected.item() == 2


@pytest.mark.parametrize("seed", range(5))
def test_crowded_enabled_card_targeting_matches_oracle(seed: int) -> None:
    rng = random.Random(8_100 + seed)
    attacker = _enabled_entity("Knight", 1, 0, 9.0, 12.0)
    names = (
        "Knight",
        "MiniPekka",
        "Pekka",
        "Valkyrie",
        "Giant",
        "HogRider",
        "Bats",
        "Cannon",
    )
    targets = [
        _enabled_entity(
            names[index % len(names)],
            index + 2,
            1,
            (5_500 + rng.randrange(7_001)) / 1_000.0,
            (8_500 + rng.randrange(7_001)) / 1_000.0,
        )
        for index in range(32)
    ]
    rng.shuffle(targets)
    ordered = [attacker, *targets]
    expected = attacker.get_nearest_target({entity.id: entity for entity in ordered})
    state = _to_tensor_state([ordered])
    selected, _ = select_stationary_targets(state, torch.tensor([0], dtype=torch.int64))
    actual = None if selected.item() < 0 else ordered[selected.item()]
    assert (None if expected is None else expected.id) == (
        None if actual is None else actual.id
    )


def test_crown_fallback_and_symmetric_building_ties_match_oracle() -> None:
    batches: list[list[Entity]] = []
    for owner in (0, 1):
        attacker = _troop(1, owner, 9.0, 16.0, sight=1.0)
        opponent = 1 - owner
        left = _building(2, opponent, 8.0, 26.0, name="Tower")
        right = _building(3, opponent, 10.0, 26.0, name="Tower")
        left._crown_tower_slot = "left"
        right._crown_tower_slot = "right"
        batches.append([attacker, left, right])

    expected_ids = [
        batches[index][0]
        .get_nearest_target({entity.id: entity for entity in batches[index]})
        .id
        for index in range(2)
    ]
    state = _to_tensor_state(batches)
    selected, fallback = select_stationary_targets(
        state, torch.tensor([0, 0], dtype=torch.int64)
    )
    actual_ids = [batches[index][selected[index].item()].id for index in range(2)]
    assert fallback.tolist() == [True, True]
    assert actual_ids == expected_ids == [2, 3]


def test_stationary_direct_hits_follow_entity_id_order_and_retarget_after_death() -> (
    None
):
    first = _troop(1, 0, 9.0, 10.0, damage=100, cooldown=0.0)
    second = _troop(2, 0, 9.0, 10.0, damage=70, cooldown=0.0)
    victim = _troop(3, 1, 9.0, 10.7, hp=100)
    reserve = _troop(4, 1, 9.0, 11.0, hp=300)
    victim.deploy_delay_remaining = 1.0
    reserve.deploy_delay_remaining = 1.0
    oracle_entities = [first, second, victim, reserve]
    tensor_entities = [
        _troop(1, 0, 9.0, 10.0, damage=100, cooldown=0.0),
        _troop(2, 0, 9.0, 10.0, damage=70, cooldown=0.0),
        _troop(3, 1, 9.0, 10.7, hp=100),
        _troop(4, 1, 9.0, 11.0, hp=300),
    ]
    tensor_entities[2].deploy_delay_remaining = 1.0
    tensor_entities[3].deploy_delay_remaining = 1.0

    battle = _attach_battle(oracle_entities)
    for entity in sorted(oracle_entities, key=lambda value: value.id):
        entity.update_combat_component(battle.dt, battle)

    state = _to_tensor_state([tensor_entities])
    result = step_stationary_combat_(state, battle.dt)
    assert result.attacked[0].tolist() == [True, True, False, False]
    assert state.target_slot[0, :2].tolist() == [2, 3]
    assert state.hp[0].tolist() == pytest.approx(
        [entity.hitpoints for entity in oracle_entities]
    )
    assert state.alive[0].tolist() == [entity.is_alive for entity in oracle_entities]
    assert state.attack_cooldown[0, :2].tolist() == pytest.approx(
        [first.attack_cooldown, second.attack_cooldown]
    )
    assert result.damage_received[0].tolist() == pytest.approx([0.0, 0.0, 100.0, 70.0])


def test_stun_observes_target_but_pauses_clock_like_oracle() -> None:
    oracle_attacker = _troop(1, 0, 9.0, 10.0, cooldown=0.4)
    oracle_target = _troop(2, 1, 9.0, 10.8)
    oracle_attacker.stun_timer = 0.5
    battle = _attach_battle([oracle_attacker, oracle_target])
    oracle_attacker.update_combat_component(battle.dt, battle)

    tensor_attacker = _troop(1, 0, 9.0, 10.0, cooldown=0.4)
    tensor_target = _troop(2, 1, 9.0, 10.8)
    tensor_attacker.stun_timer = 0.5
    state = _to_tensor_state([[tensor_attacker, tensor_target]])
    step_stationary_combat_(state, battle.dt)
    assert state.target_slot[0, 0].item() == 1
    assert oracle_attacker.target_id == 2
    assert state.attack_cooldown[0, 0].item() == oracle_attacker.attack_cooldown
    assert state.last_attack_time[0, 0].item() == oracle_attacker.last_attack_time


def test_direct_area_hit_snapshots_all_stationary_recipients() -> None:
    oracle_attacker = _troop(1, 0, 9.0, 10.0, damage=90, cooldown=0.0)
    tensor_attacker = _troop(1, 0, 9.0, 10.0, damage=90, cooldown=0.0)
    oracle_attacker.card_stats.area_damage_radius = 1_000
    tensor_attacker.card_stats.area_damage_radius = 1_000
    oracle_targets = [
        _troop(2, 1, 9.0, 10.8),
        _troop(3, 1, 9.7, 10.8),
        _building(4, 1, 10.8, 10.8),
        _troop(5, 1, 12.0, 10.8),
    ]
    tensor_targets = [
        _troop(2, 1, 9.0, 10.8),
        _troop(3, 1, 9.7, 10.8),
        _building(4, 1, 10.8, 10.8),
        _troop(5, 1, 12.0, 10.8),
    ]
    for target in [*oracle_targets, *tensor_targets]:
        target.deploy_delay_remaining = 1.0
    battle = _attach_battle([oracle_attacker, *oracle_targets])
    oracle_attacker.update_combat_component(battle.dt, battle)

    state = _to_tensor_state([[tensor_attacker, *tensor_targets]])
    result = step_stationary_combat_(state, battle.dt)
    assert state.hp[0].tolist() == pytest.approx(
        [oracle_attacker.hitpoints, *[target.hitpoints for target in oracle_targets]]
    )
    assert result.damage_received[0].tolist() == pytest.approx(
        [0.0, 90.0, 90.0, 90.0, 0.0]
    )


def test_projectile_lethal_reservation_aggregates_and_applies_native_gates() -> None:
    reserved = projectile_lethal_reservations(
        target_hp=torch.tensor([[100.0, 100.0, 100.0]], dtype=torch.float64),
        target_alive=torch.tensor([[True, True, True]]),
        target_shield_hp=torch.tensor([[0.0, 10.0, 0.0]], dtype=torch.float64),
        prior_max_duration_ms=torch.tensor([[0, 0, 700]], dtype=torch.int64),
        projectile_active=torch.tensor([[True, True, True, True]]),
        projectile_reserves_damage=torch.tensor([[True, True, True, True]]),
        projectile_target_slot=torch.tensor([[0, 0, 1, 2]], dtype=torch.int64),
        projectile_expected_damage=torch.tensor(
            [[60.0, 40.0, 150.0, 150.0]], dtype=torch.float64
        ),
        projectile_duration_ms=torch.tensor([[300, 400, 300, 300]]),
    )
    assert reserved.tolist() == [[True, False, False]]


@pytest.mark.parametrize(
    "device",
    (
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ),
)
def test_attack_clock_uses_exact_windup_and_projectile_keep_boundaries(
    device: str,
) -> None:
    # Rows exercise direct windup at +25, ordinary retained acquisition at
    # that same position, direct windup one unit outside, and a projectile
    # cycle at its native +500 boundary.
    state = StationaryCombatState.empty(4, 2, device=device)
    state.present[:] = True
    state.alive[:] = True
    state.entity_id[:, 0] = 1
    state.entity_id[:, 1] = 2
    state.owner[:, 1] = 1
    state.x_units[:, 0] = 10_000
    state.x_units[:, 1] = torch.tensor(
        [11_375, 11_375, 11_376, 11_850],
        dtype=torch.int64,
        device=device,
    )
    state.collision_radius_units[:, 1] = 600
    state.range_units[:, 0] = 750
    state.sight_range_units[:, 0] = 5_500
    state.target_slot[:, 0] = 1
    state.attack_cooldown[:, 0] = 0.3
    state.first_hit_ms[:, 0] = 300
    state.hit_speed_ms[:, 0] = 1_000
    state.attack_windup_active[[0, 2], 0] = True
    state.started_projectile_hit_cycle[3, 0] = True
    state.uses_projectile[3, 0] = True
    state.combat_enabled[:, 1] = False

    result = step_stationary_combat_(state)

    assert result.attack_clock_in_range is not None
    assert result.attack_clock_in_range[:, 0].tolist() == [True, False, False, True]
    assert state.attack_cooldown[:, 0].tolist() == pytest.approx([0.25, 0.3, 0.3, 0.25])
    assert state.attack_windup_active[:, 0].tolist() == [True, False, False, True]


def test_support_mask_rejects_a_mixed_unsupported_row_before_mutation() -> None:
    state = StationaryCombatState.empty(2, 2)
    state.present[:, 0] = True
    state.alive[:, 0] = True
    state.entity_id[:, 0] = 1
    state.hp[:, 0] = 100.0
    state.max_hp[:, 0] = 100.0
    state.ordinary_combat_supported[1, 0] = False
    before = state.hp.clone()
    assert stationary_combat_support_mask(state).tolist() == [True, False]
    with pytest.raises(UnsupportedStationaryCombatError) as exc_info:
        step_stationary_combat_(state)
    assert exc_info.value.batch_indices == [1]
    assert torch.equal(state.hp, before)


def test_randomized_batched_stationary_mutations_match_oracle() -> None:
    rng = random.Random(947_221)
    oracle_batches: list[list[Entity]] = []
    tensor_batches: list[list[Entity]] = []
    for _ in range(12):
        oracle_entities: list[Entity] = []
        tensor_entities: list[Entity] = []
        for entity_id in (1, 2, 3):
            x = (8_500 + rng.randrange(1_001)) / 1_000.0
            y = (9_500 + rng.randrange(501)) / 1_000.0
            damage = rng.choice((35, 70, 110))
            cooldown = rng.choice((0.0, 0.05, 0.2))
            oracle_attacker = _troop(
                entity_id,
                0,
                x,
                y,
                damage=damage,
                attack_range=1.5,
                cooldown=cooldown,
            )
            tensor_attacker = _troop(
                entity_id,
                0,
                x,
                y,
                damage=damage,
                attack_range=1.5,
                cooldown=cooldown,
            )
            if rng.random() < 0.2:
                oracle_attacker.stun_timer = 0.3
                tensor_attacker.stun_timer = 0.3
            oracle_entities.append(oracle_attacker)
            tensor_entities.append(tensor_attacker)
        for entity_id in range(10, 16):
            x = (8_300 + rng.randrange(1_401)) / 1_000.0
            y = (10_300 + rng.randrange(1_201)) / 1_000.0
            hp = rng.choice((60, 100, 180, 300))
            oracle_target = _troop(entity_id, 1, x, y, hp=hp)
            tensor_target = _troop(entity_id, 1, x, y, hp=hp)
            oracle_target.deploy_delay_remaining = 1.0
            tensor_target.deploy_delay_remaining = 1.0
            oracle_entities.append(oracle_target)
            tensor_entities.append(tensor_target)
        permutation = list(range(len(oracle_entities)))
        rng.shuffle(permutation)
        oracle_batches.append([oracle_entities[index] for index in permutation])
        tensor_batches.append([tensor_entities[index] for index in permutation])

    for entities in oracle_batches:
        battle = _attach_battle(entities)
        for entity in sorted(entities, key=lambda value: value.id):
            entity.update_combat_component(battle.dt, battle)

    state = _to_tensor_state(tensor_batches)
    step_stationary_combat_(state)
    for batch_index, (oracle_entities, tensor_entities) in enumerate(
        zip(oracle_batches, tensor_batches, strict=True)
    ):
        oracle_by_id = {entity.id: entity for entity in oracle_entities}
        slot_by_id = {entity.id: slot for slot, entity in enumerate(tensor_entities)}
        for entity_id, oracle_entity in oracle_by_id.items():
            slot = slot_by_id[entity_id]
            assert state.hp[batch_index, slot].item() == pytest.approx(
                oracle_entity.hitpoints
            )
            assert state.alive[batch_index, slot].item() is oracle_entity.is_alive
            assert state.attack_cooldown[batch_index, slot].item() == pytest.approx(
                oracle_entity.attack_cooldown
            )
            tensor_target_slot = state.target_slot[batch_index, slot].item()
            tensor_target_id = (
                None
                if tensor_target_slot < 0
                else tensor_entities[tensor_target_slot].id
            )
            assert tensor_target_id == oracle_entity.target_id


@pytest.mark.skipif(not torch.backends.mps.is_available(), reason="MPS unavailable")
def test_exact_float64_state_fails_closed_on_mps() -> None:
    with pytest.raises(ValueError, match="requires CPU/CUDA float64"):
        StationaryCombatState.empty(1, 2, device="mps")


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_exact_float64_combat_state_is_cuda_resident() -> None:
    state = StationaryCombatState.empty(2, 4, device="cuda")

    assert state.device.type == "cuda"
    assert state.hp.dtype == torch.float64
    assert stationary_combat_support_mask(state).tolist() == [True, True]


def test_lower_id_direct_hit_activates_king_before_its_component_turn() -> None:
    state = StationaryCombatState.empty(1, 2)
    state.present[0] = True
    state.alive[0] = True
    state.entity_id[0] = torch.tensor([1, 3])
    state.kind[0] = torch.tensor([0, 1], dtype=torch.int8)
    state.owner[0] = torch.tensor([0, 1], dtype=torch.int8)
    state.x_units[0] = torch.tensor([9_000, 9_000])
    state.y_units[0] = torch.tensor([15_000, 15_500])
    state.hp[0] = torch.tensor([500.0, 2_000.0], dtype=torch.float64)
    state.max_hp[0] = state.hp[0]
    state.damage[0, 0] = 100.0
    state.range_units[0, 0] = 1_000
    state.sight_range_units[0, 0] = 5_500
    state.attack_cooldown[0, 0] = 0.0
    state.hit_speed_ms[0, 0] = 1_000
    state.target_slot[0, 0] = 1
    state.tower_active[0, 1] = False
    state.requires_activation[0, 1] = True
    state.activation_delay_seconds[0, 1] = 3.3
    state.activation_first_hit_delay_seconds[0, 1] = 0.7

    result = step_stationary_combat_(state)

    assert result.damage_received[0].tolist() == [0.0, 100.0]
    assert state.tower_active[0, 1].item() is True
    # Attacker ID 1 wakes King ID 3 before the King's component rank, so the
    # activation action consumes this same 50 ms frame.
    assert state.activation_delay_remaining[0, 1].item() == 3.25
    assert state.activation_first_hit_delay_remaining[0, 1].item() == 0.7
    assert state.last_attack_time[0, 1].item() == 0.0


def test_activation_and_first_hit_delays_feed_only_remainder_to_combat() -> None:
    state = StationaryCombatState.empty(1, 1)
    state.present[0, 0] = True
    state.alive[0, 0] = True
    state.entity_id[0, 0] = 3
    state.kind[0, 0] = 1
    state.tower_active[0, 0] = True
    state.requires_activation[0, 0] = True
    state.activation_delay_remaining[0, 0] = 0.02
    state.activation_first_hit_delay_remaining[0, 0] = 0.02
    state.attack_cooldown[0, 0] = 0.5

    result = step_stationary_combat_(state)

    assert not result.attacked.any().item()
    assert state.activation_delay_remaining[0, 0].item() == 0.0
    assert state.activation_first_hit_delay_remaining[0, 0].item() == 0.0
    assert state.attack_cooldown[0, 0].item() == 0.0
    assert state.last_attack_time[0, 0].item() == pytest.approx(0.01)
