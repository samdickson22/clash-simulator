from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Projectile, Troop
from clasher.torch_sim.resident_archer_queen import (
    ArcherQueenReason,
    TensorArcherQueenState,
    activate_archer_queen_,
    step_archer_queen_,
)
from clasher.torch_sim.runtime_state import TensorBattleRuntime


def _battle(*rows: tuple[str, int, float]) -> BattleState:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    battle._champion_ability_owner_ids.clear()
    battle.fast_path = False
    for name, player, x in rows:
        stats = battle.card_loader.get_card(name)
        assert stats is not None
        entity = battle._spawn_entity(Troop, Position(x, 12.0), player, stats)
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
    return battle


def _mechanic(entity: Troop) -> Any:
    return next(
        item for item in entity.mechanics if type(item).__name__ == "ArcherQueenCloak"
    )


def _slot(runtime: TensorBattleRuntime, entity_id: int, row: int = 0) -> int:
    matches = torch.nonzero(
        runtime.battle.entity_id[row] == entity_id, as_tuple=False
    ).flatten()
    assert matches.numel() == 1
    return int(matches.item())


def _projectiles(battle: BattleState) -> list[Projectile]:
    return [
        entity for entity in battle.entities.values() if isinstance(entity, Projectile)
    ]


def _tensor_projectiles(
    state: TensorArcherQueenState, row: int = 0
) -> list[tuple[int, float, float, int]]:
    return [
        (
            int(state.projectile_id[row, slot].item()),
            int(state.projectile_x_units[row, slot].item()) / 1_000,
            int(state.projectile_y_units[row, slot].item()) / 1_000,
            int(state.projectile_target_id[row, slot].item()),
        )
        for slot in range(state.max_projectiles)
        if bool(state.projectile_active[row, slot].item())
    ]


def test_exact_full_cloak_attack_projectile_and_impact_lifecycle() -> None:
    candidate = _battle(("ArcherQueen", 0, 8.0), ("Knight", 1, 12.0))
    candidate.players[0].elixir = 10.0
    oracle = deepcopy(candidate)
    queen_id, target_id = tuple(candidate.entities)
    oracle_queen = oracle.entities[queen_id]
    oracle_target = oracle.entities[target_id]
    assert isinstance(oracle_queen, Troop)
    assert isinstance(oracle_target, Troop)
    oracle_cloak = _mechanic(oracle_queen)
    runtime = TensorBattleRuntime.from_battles(
        [candidate], max_entities=16, event_capacity=512
    )
    state = TensorArcherQueenState.from_battles(runtime, [candidate])
    queen_slot = _slot(runtime, queen_id)
    target_slot = _slot(runtime, target_id)

    assert oracle.activate_champion_ability(0)
    activated = activate_archer_queen_(state, runtime, torch.tensor([[True, False]]))
    assert activated[0, queen_slot]
    assert runtime.battle.elixir[0, 0].item() == oracle.players[0].elixir

    saw_launch = False
    saw_impact = False
    for _ in range(90):
        oracle._step_logic_tick()
        result = step_archer_queen_(state, runtime)
        saw_launch |= bool(result.launched.any().item())
        saw_impact |= bool(result.impacted.any().item())
        target_tensor_slot = int(state.combat.target_slot[0, queen_slot].item())
        tensor_target_id = (
            None
            if target_tensor_slot < 0
            else int(runtime.battle.entity_id[0, target_tensor_slot].item())
        )
        assert tensor_target_id == oracle_queen.target_id
        assert state.combat.attack_cooldown[0, queen_slot].item() == pytest.approx(
            oracle_queen.attack_cooldown, abs=1e-12
        )
        assert runtime.battle.entity_last_attack_time[
            0, queen_slot
        ].item() == pytest.approx(oracle_queen.last_attack_time, abs=1e-12)
        assert runtime.battle.entity_hp[0, target_slot].item() == float(
            oracle_target.hitpoints
        )
        assert state.mechanics.attack_mode_multiplier[
            0, queen_slot
        ].item() == pytest.approx(oracle_queen.attack_mode_multiplier)
        assert state.mechanics.movement_mode_multiplier[
            0, queen_slot
        ].item() == pytest.approx(oracle_queen.movement_mode_multiplier)
        assert state.mechanics.stealth_until_ms[0, queen_slot].item() == int(
            oracle_queen.__dict__["_stealth_until"]
        )
        ability = oracle_cloak.ability
        assert state.mechanics.ability_active[0, queen_slot].item() == bool(
            ability.is_active
        )
        oracle_objects = [
            (item.id, item.position.x, item.position.y, item.primary_target.id)
            for item in _projectiles(oracle)
            if item.primary_target is not None
        ]
        assert _tensor_projectiles(state) == oracle_objects
        assert set(
            runtime.battle.entity_id[0, runtime.entity_pool.active[0]].tolist()
        ) == set(oracle.entities)

    assert saw_launch and saw_impact


def test_activation_deadlines_cancel_and_hidden_projection_match_oracle() -> None:
    candidate = _battle(("ArcherQueen", 0, 8.0), ("Knight", 1, 12.0))
    candidate.players[0].elixir = 4.0
    oracle = deepcopy(candidate)
    queen_id = next(iter(candidate.entities))
    oracle_queen = oracle.entities[queen_id]
    assert isinstance(oracle_queen, Troop)
    oracle_cloak = _mechanic(oracle_queen)
    runtime = TensorBattleRuntime.from_battles(
        [candidate], max_entities=8, event_capacity=128
    )
    state = TensorArcherQueenState.from_battles(runtime, [candidate])
    queen_slot = _slot(runtime, queen_id)

    assert oracle.activate_champion_ability(0)
    activate_archer_queen_(state, runtime, torch.tensor([[True, False]]))
    assert runtime.battle.elixir[0, 0].item() == 3.0
    assert state.mechanics.cloak_pending_until_ms[0, queen_slot].item() == 200
    assert state.mechanics.cast_lock_until_ms[0, queen_slot].item() == 933

    oracle.time = 0.05
    oracle_cloak.ability.cancel_before_effect()
    runtime.battle.time[0] = 0.05
    result = step_archer_queen_(
        state,
        runtime,
        cancel_before_effect=torch.nn.functional.one_hot(
            torch.tensor([queen_slot]), num_classes=runtime.max_entities
        ).to(torch.bool),
    )
    assert result.committed.item()
    assert not state.mechanics.ability_active[0, queen_slot]
    assert state.mechanics.cloak_pending_until_ms[0, queen_slot].item() == -1
    assert not state.mechanics.hidden_from_enemies(runtime)[0, queen_slot]
    assert not state.mechanics.combat_blocked()[0, queen_slot]


def test_death_cancels_cloak_and_transfers_newest_live_owner() -> None:
    battle = _battle(
        ("ArcherQueen", 0, 7.0),
        ("ArcherQueen", 0, 8.0),
        ("Knight", 1, 12.0),
    )
    battle.players[0].elixir = 10.0
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=12, event_capacity=256
    )
    state = TensorArcherQueenState.from_battles(runtime, [battle])
    first_id, second_id, _ = tuple(battle.entities)
    first_slot = _slot(runtime, first_id)
    second_slot = _slot(runtime, second_id)
    activated = activate_archer_queen_(state, runtime, torch.tensor([[True, False]]))
    assert activated[0, second_slot]
    runtime.battle.entity_active[0, second_slot] = False

    step_archer_queen_(state, runtime)

    key = int(state.mechanics.ability_key[0, first_slot].item())
    assert state.mechanics.recorded_owner_id[0, 0, key].item() == first_id
    assert not state.mechanics.ability_active[0, second_slot]
    assert not runtime.entity_pool.active[0, second_slot]


def test_mixed_unsupported_row_and_capacity_failure_are_atomic() -> None:
    supported = _battle(("ArcherQueen", 0, 8.0), ("Knight", 1, 12.0))
    unsupported = _battle(("ArcherQueen", 0, 8.0), ("DarkPrince", 1, 12.0))
    runtime = TensorBattleRuntime.from_battles(
        [supported, unsupported], max_entities=8, event_capacity=128
    )
    state = TensorArcherQueenState.from_battles(runtime, [supported, unsupported])
    unsupported_time = runtime.battle.time[1].clone()
    unsupported_combat = state.combat.target_slot[1].clone()

    result = step_archer_queen_(state, runtime)

    assert result.committed.tolist() == [True, False]
    assert result.reason.tolist() == [0, int(ArcherQueenReason.UNSUPPORTED_PAYLOAD)]
    assert runtime.battle.time[0].item() == 0.05
    assert torch.equal(runtime.battle.time[1], unsupported_time)
    assert torch.equal(state.combat.target_slot[1], unsupported_combat)

    tiny = TensorBattleRuntime.from_battles(
        [supported], max_entities=8, event_capacity=1
    )
    tiny_state = TensorArcherQueenState.from_battles(tiny, [supported])
    before = tiny.clone()
    rejected = step_archer_queen_(tiny_state, tiny)
    assert rejected.reason.item() == int(ArcherQueenReason.EVENT_CAPACITY)
    assert torch.equal(tiny.battle.time, before.battle.time)
    assert torch.equal(tiny.battle.entity_hp, before.battle.entity_hp)


def test_clone_fork_and_reset_are_independent() -> None:
    battle = _battle(("ArcherQueen", 0, 8.0), ("Knight", 1, 12.0))
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=8)
    state = TensorArcherQueenState.from_battles(runtime, [battle])
    clone = state.clone()
    clone.combat.attack_cooldown.zero_()
    assert not torch.equal(clone.combat.attack_cooldown, state.combat.attack_cooldown)
    assert clone.catalog is state.catalog
    fork = state.fork([0, 0])
    assert fork.batch_size == 2
    fork.projectile_id.fill_(99)
    state.reset_rows_([0], clone, [0])
    assert state.combat.attack_cooldown.sum().item() == 0.0
    assert state.projectile_id.max().item() == 0


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_full_lifecycle_smoke() -> None:
    battle = _battle(("ArcherQueen", 0, 8.0), ("Knight", 1, 12.0))
    battle.players[0].elixir = 10.0
    runtime = TensorBattleRuntime.from_battles(
        [battle], device="cuda", max_entities=8, event_capacity=256
    )
    state = TensorArcherQueenState.from_battles(runtime, [battle])
    activate_archer_queen_(state, runtime, torch.tensor([[True, False]], device="cuda"))
    for _ in range(30):
        result = step_archer_queen_(state, runtime)
    assert result.committed.device.type == "cuda"
    assert state.projectile_active.device.type == "cuda"
