from __future__ import annotations

from copy import deepcopy

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.torch_sim.runtime_mechanics import (
    MechanicEventPayload,
    TensorRuntimeMechanics,
    UnsupportedMechanicDeviceError,
    validate_mechanic_device,
)
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
)


def _empty_battle() -> BattleState:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    battle._champion_ability_owner_ids.clear()
    return battle


def _spawn(
    battle: BattleState,
    name: str,
    player_id: int,
    x: float,
    y: float,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = battle._spawn_entity(Troop, Position(x, y), player_id, stats)
    assert isinstance(entity, Troop)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _slot(runtime: TensorBattleRuntime, entity_id: int, row: int = 0) -> int:
    matches = torch.nonzero(
        runtime.battle.entity_id[row] == entity_id, as_tuple=False
    ).flatten()
    assert matches.numel() == 1
    return int(matches.item())


def _mechanic(entity: Troop, operation: str) -> object:
    return next(item for item in entity.mechanics if type(item).__name__ == operation)


def test_boundary_compiles_generalized_mechanic_planes_without_card_switches() -> None:
    battle = _empty_battle()
    shield = _spawn(battle, "DarkPrince", 0, 7.0, 12.0)
    on_hit = _spawn(battle, "ElectroWizard", 1, 9.0, 12.0)
    champion = _spawn(battle, "ArcherQueen", 0, 11.0, 12.0)
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=16)

    phase = TensorRuntimeMechanics.from_battles(runtime, [battle])

    shield_slot = _slot(runtime, shield.id)
    hit_slot = _slot(runtime, on_hit.id)
    champion_slot = _slot(runtime, champion.id)
    assert phase.has_shield[0, shield_slot]
    assert phase.shield_current[0, shield_slot].item() == getattr(
        _mechanic(shield, "Shield"), "current_shield"
    )
    assert phase._source_has_on_hit(
        phase.entity_mechanic_card[:, hit_slot : hit_slot + 1]
    ).item()
    assert phase.has_ability[0, champion_slot]
    assert phase.cloak_mask[0, champion_slot]
    assert phase.attack_speed_multiplier[0, champion_slot].item() == pytest.approx(
        getattr(_mechanic(champion, "ArcherQueenCloak"), "attack_speed_multiplier")
    )
    phase.assert_invariants(runtime)


def test_ordered_shield_hits_then_serialized_on_hit_status_match_oracle() -> None:
    candidate = _empty_battle()
    source = _spawn(candidate, "ElectroWizard", 0, 8.0, 12.0)
    target = _spawn(candidate, "DarkPrince", 1, 9.0, 12.0)
    oracle = deepcopy(candidate)
    oracle_source = oracle.entities[source.id]
    oracle_target = oracle.entities[target.id]
    assert isinstance(oracle_source, Troop)
    assert isinstance(oracle_target, Troop)
    oracle_on_hit = _mechanic(oracle_source, "SerializedOnHitBuff")
    oracle_shield = _mechanic(oracle_target, "Shield")
    shield_hp = float(getattr(oracle_shield, "current_shield"))
    hits = (shield_hp / 2.0, shield_hp, 37.0)
    for amount in hits:
        oracle_target.take_damage(amount)
        getattr(oracle_on_hit, "on_attack_hit")(oracle_source, oracle_target)

    runtime = TensorBattleRuntime.from_battles(
        [candidate], max_entities=8, event_capacity=16
    )
    phase = TensorRuntimeMechanics.from_battles(runtime, [candidate])
    source_slot = _slot(runtime, source.id)
    target_slot = _slot(runtime, target.id)
    result = phase.resolve_attack_hits_(
        runtime,
        source_slot=torch.full((1, 3), source_slot),
        target_slot=torch.full((1, 3), target_slot),
        incoming_damage=torch.tensor([hits], dtype=torch.float64),
    )

    assert result.shield_absorbed.tolist() == [[True, True, False]]
    assert result.shield_broken.tolist() == [[False, True, False]]
    assert result.hitpoint_damage.tolist() == [[0.0, 0.0, 37.0]]
    assert result.status_dispatched.tolist() == [[True, True, True]]
    assert phase.shield_current[0, target_slot].item() == getattr(
        oracle_shield, "current_shield"
    )
    assert phase.shield_break_count[0, target_slot].item() == getattr(
        oracle_target, "_shield_break_count"
    )
    assert runtime.battle.entity_hp[0, target_slot].item() == oracle_target.hitpoints
    assert runtime.status.stun_timer[0, target_slot].item() == oracle_target.stun_timer
    assert runtime.status.slow_timer[0, target_slot].item() == oracle_target.slow_timer

    count = int(runtime.events.count[0].item())
    assert count == 6
    assert runtime.events.payload[0, :count].tolist() == [
        int(MechanicEventPayload.SHIELD_ABSORBED),
        int(MechanicEventPayload.SERIALIZED_ON_HIT_STATUS),
        int(MechanicEventPayload.SHIELD_BROKEN),
        int(MechanicEventPayload.SERIALIZED_ON_HIT_STATUS),
        0,
        int(MechanicEventPayload.SERIALIZED_ON_HIT_STATUS),
    ]
    assert runtime.events.opcode[0, :count].tolist() == [
        int(RuntimeEventOpcode.STATUS),
        int(RuntimeEventOpcode.STATUS),
        int(RuntimeEventOpcode.STATUS),
        int(RuntimeEventOpcode.STATUS),
        int(RuntimeEventOpcode.DAMAGE),
        int(RuntimeEventOpcode.STATUS),
    ]

    runtime.sync_to_battles([candidate])
    phase.sync_to_battles(runtime, [candidate])
    candidate_target = candidate.entities[target.id]
    assert isinstance(candidate_target, Troop)
    assert candidate_target.hitpoints == oracle_target.hitpoints
    assert candidate_target.stun_timer == oracle_target.stun_timer
    assert candidate_target.slow_timer == oracle_target.slow_timer
    assert getattr(_mechanic(candidate_target, "Shield"), "current_shield") == getattr(
        oracle_shield, "current_shield"
    )


def test_hit_event_capacity_overflow_is_fail_closed_before_any_mutation() -> None:
    battle = _empty_battle()
    source = _spawn(battle, "ElectroWizard", 0, 8.0, 12.0)
    target = _spawn(battle, "DarkPrince", 1, 9.0, 12.0)
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=8, event_capacity=1
    )
    phase = TensorRuntimeMechanics.from_battles(runtime, [battle])
    before = (
        runtime.battle.entity_hp.clone(),
        phase.shield_current.clone(),
        runtime.status.stun_timer.clone(),
        runtime.events.count.clone(),
    )

    with pytest.raises(OverflowError, match="event capacity"):
        phase.resolve_attack_hits_(
            runtime,
            source_slot=torch.tensor([[_slot(runtime, source.id)]]),
            target_slot=torch.tensor([[_slot(runtime, target.id)]]),
            incoming_damage=torch.tensor([[10.0]], dtype=torch.float64),
        )

    assert torch.equal(runtime.battle.entity_hp, before[0])
    assert torch.equal(phase.shield_current, before[1])
    assert torch.equal(runtime.status.stun_timer, before[2])
    assert torch.equal(runtime.events.count, before[3])


def test_status_guard_is_independent_from_whole_hit_shield_eligibility() -> None:
    battle = _empty_battle()
    source = _spawn(battle, "ElectroWizard", 0, 8.0, 12.0)
    target = _spawn(battle, "DarkPrince", 1, 9.0, 12.0)
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=8, event_capacity=4
    )
    phase = TensorRuntimeMechanics.from_battles(runtime, [battle])

    result = phase.resolve_attack_hits_(
        runtime,
        source_slot=torch.tensor([[_slot(runtime, source.id)]]),
        target_slot=torch.tensor([[_slot(runtime, target.id)]]),
        incoming_damage=torch.tensor([[10.0]], dtype=torch.float64),
        status_eligible=False,
    )

    assert result.shield_absorbed.item()
    assert not result.status_dispatched.item()
    assert runtime.status.stun_timer.max().item() == 0.0
    assert runtime.status.slow_timer.max().item() == 0.0
    assert runtime.events.count.tolist() == [1]


def test_cloak_activation_lifecycle_planes_events_and_sync_match_oracle() -> None:
    candidate = _empty_battle()
    queen = _spawn(candidate, "ArcherQueen", 0, 9.0, 12.0)
    candidate.players[0].elixir = 10.0
    oracle = deepcopy(candidate)
    oracle_queen = oracle.entities[queen.id]
    assert isinstance(oracle_queen, Troop)
    oracle_mechanic = _mechanic(oracle_queen, "ArcherQueenCloak")
    runtime = TensorBattleRuntime.from_battles(
        [candidate], max_entities=8, event_capacity=32
    )
    phase = TensorRuntimeMechanics.from_battles(runtime, [candidate])
    queen_slot = _slot(runtime, queen.id)

    assert oracle.activate_champion_ability(0)
    activated = phase.activate_(runtime, torch.tensor([[True, False]]))
    assert activated.activated[0, queen_slot]
    assert runtime.battle.elixir[0, 0].item() == oracle.players[0].elixir
    assert (
        phase.last_use_time_ms[0, queen_slot].item()
        == getattr(oracle_mechanic, "ability").last_use_time
    )
    assert phase.cloak_pending_until_ms[0, queen_slot].item() == getattr(
        oracle_mechanic, "_cloak_pending_until"
    )

    for deadline_ms in (199, 200, 900, 950, 3_650, 3_700):
        oracle.time = deadline_ms / 1000.0
        runtime.battle.time[0] = oracle.time
        getattr(oracle_mechanic, "on_tick")(oracle_queen, 50)
        phase.tick_cloak_(runtime)
        assert (
            phase.ability_active[0, queen_slot].item()
            == getattr(oracle_mechanic, "ability").is_active
        )
        assert phase.attack_mode_multiplier[0, queen_slot].item() == pytest.approx(
            oracle_queen.attack_mode_multiplier
        )
        assert phase.movement_mode_multiplier[0, queen_slot].item() == pytest.approx(
            oracle_queen.movement_mode_multiplier
        )
        assert phase.stealth_until_ms[0, queen_slot].item() == getattr(
            oracle_queen, "_stealth_until"
        )

    payloads = runtime.events.payload[0, : runtime.events.count[0]].tolist()
    assert int(MechanicEventPayload.CHAMPION_ACTIVATED) in payloads
    assert int(MechanicEventPayload.CLOAK_STARTED) in payloads
    assert int(MechanicEventPayload.CAST_LOCK_ENDED) in payloads
    assert int(MechanicEventPayload.CLOAK_ENDED) in payloads

    runtime.sync_to_battles([candidate])
    phase.sync_to_battles(runtime, [candidate])
    candidate_queen = candidate.entities[queen.id]
    assert isinstance(candidate_queen, Troop)
    candidate_mechanic = _mechanic(candidate_queen, "ArcherQueenCloak")
    assert candidate_queen.attack_mode_multiplier == oracle_queen.attack_mode_multiplier
    assert (
        candidate_queen.movement_mode_multiplier
        == oracle_queen.movement_mode_multiplier
    )
    assert getattr(candidate_queen, "_stealth_until") == getattr(
        oracle_queen, "_stealth_until"
    )
    assert (
        getattr(candidate_mechanic, "ability").is_active
        == getattr(oracle_mechanic, "ability").is_active
    )


def test_duplicate_champion_ownership_transfer_and_activation_match_oracle() -> None:
    candidate = _empty_battle()
    first = _spawn(candidate, "ArcherQueen", 0, 7.0, 12.0)
    second = _spawn(candidate, "ArcherQueen", 0, 9.0, 12.0)
    candidate.players[0].elixir = 10.0
    oracle = deepcopy(candidate)
    oracle.entities[second.id].is_alive = False
    oracle.entities[first.id].is_alive = True
    assert oracle.activate_champion_ability(0)

    runtime = TensorBattleRuntime.from_battles(
        [candidate], max_entities=8, event_capacity=16
    )
    phase = TensorRuntimeMechanics.from_battles(runtime, [candidate])
    runtime.battle.entity_active[0, _slot(runtime, second.id)] = False
    result = phase.activate_(runtime, torch.tensor([[True, False]]))

    first_slot = _slot(runtime, first.id)
    assert result.transferred[0, first_slot]
    assert result.activated[0, first_slot]
    assert phase.recorded_owner_id[0, 0, phase.ability_key[0, first_slot]].item() == (
        first.id
    )


def test_clone_is_independent_and_shares_immutable_catalogs() -> None:
    battle = _empty_battle()
    _spawn(battle, "DarkPrince", 0, 8.0, 12.0)
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=8)
    phase = TensorRuntimeMechanics.from_battles(runtime, [battle])

    cloned = phase.clone()
    cloned.shield_current.zero_()

    assert cloned.catalog is phase.catalog
    assert cloned.on_hit_catalog is phase.on_hit_catalog
    assert not torch.equal(cloned.shield_current, phase.shield_current)


def test_row_selective_multi_fork_matches_runtime_search_branch_order() -> None:
    first = _empty_battle()
    _spawn(first, "DarkPrince", 0, 8.0, 12.0)
    second = deepcopy(first)
    runtime = TensorBattleRuntime.from_battles([first, second], max_entities=8)
    phase = TensorRuntimeMechanics.from_battles(runtime, [first, second])
    phase.shield_break_count[0].fill_(1)
    phase.shield_break_count[1].fill_(2)

    forked = phase.fork([1, 0], copies=2)

    assert forked.batch_size == 4
    assert forked.shield_break_count[:, 0].tolist() == [2, 2, 1, 1]
    assert forked.catalog is phase.catalog
    assert forked.on_hit_catalog is phase.on_hit_catalog
    forked.shield_break_count.zero_()
    assert phase.shield_break_count[:, 0].tolist() == [1, 2]


def test_reused_slot_initializes_new_entity_mechanics_from_serialized_catalog() -> None:
    battle = _empty_battle()
    shield = _spawn(battle, "DarkPrince", 0, 8.0, 12.0)
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=4)
    phase = TensorRuntimeMechanics.from_battles(runtime, [battle])
    slot = _slot(runtime, shield.id)
    maximum = phase.shield_max[0, slot].item()
    phase.shield_current[0, slot] = 0.0
    phase.shield_break_count[0, slot] = 5
    runtime.battle.entity_id[0, slot] = 99

    new = phase.refresh_new_entities_(runtime)

    assert new[0, slot]
    assert phase.initialized_entity_id[0, slot].item() == 99
    assert phase.shield_current[0, slot].item() == maximum
    assert phase.shield_break_count[0, slot].item() == 0


def test_mps_is_always_fail_closed_before_mechanic_mutation() -> None:
    with pytest.raises(UnsupportedMechanicDeviceError, match="fail closed on MPS"):
        validate_mechanic_device("mps")


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_retained_shield_and_on_hit_status_path() -> None:
    battle = _empty_battle()
    source = _spawn(battle, "ElectroWizard", 0, 8.0, 12.0)
    target = _spawn(battle, "DarkPrince", 1, 9.0, 12.0)
    runtime = TensorBattleRuntime.from_battles(
        [battle], device="cuda", max_entities=8, event_capacity=8
    )
    phase = TensorRuntimeMechanics.from_battles(runtime, [battle])

    result = phase.resolve_attack_hits_(
        runtime,
        source_slot=torch.tensor([[_slot(runtime, source.id)]], device="cuda"),
        target_slot=torch.tensor([[_slot(runtime, target.id)]], device="cuda"),
        incoming_damage=torch.tensor([[10.0]], dtype=torch.float64, device="cuda"),
    )

    assert result.shield_absorbed.device.type == "cuda"
    assert result.shield_absorbed.item()
    assert runtime.status.stun_timer.device.type == "cuda"
