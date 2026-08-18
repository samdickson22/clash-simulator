from __future__ import annotations

from collections.abc import Iterator

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.factory.dynamic_factory import troop_from_character_data
from clasher.spells import SPELL_REGISTRY, SpawnProjectileSpell
from clasher.torch_sim.combat_clock_transitions import (
    TensorCombatClockPlanes,
    apply_forced_movement_interrupt_,
    apply_stun_interrupt_,
    initialize_spawned_attack_clocks_,
)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    yield device


def _knight() -> tuple[BattleState, Troop]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    entity = battle._spawn_entity(Troop, Position(9.0, 10.0), 1, stats)
    assert isinstance(entity, Troop)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return battle, entity


def _planes(
    device: str,
    *,
    cooldown: float,
    target: int,
    windup: bool,
    preload_blocked: bool,
    attacked: bool,
) -> TensorCombatClockPlanes:
    return TensorCombatClockPlanes(
        attack_cooldown=torch.tensor([[cooldown]], dtype=torch.float64, device=device),
        target_slot=torch.tensor([[target]], dtype=torch.int64, device=device),
        attack_windup_active=torch.tensor([[windup]], dtype=torch.bool, device=device),
        attack_preload_blocked=torch.tensor(
            [[preload_blocked]], dtype=torch.bool, device=device
        ),
        has_attacked_once=torch.tensor([[attacked]], dtype=torch.bool, device=device),
    )


def test_due_stun_interrupt_matches_scalar_combat_clock(tensor_device: str) -> None:
    _, scalar = _knight()
    scalar.attack_cooldown = 10.0
    scalar.target_id = 99
    scalar.__dict__["_last_combat_target_id"] = 99
    scalar._attack_windup_active = True
    scalar._attack_preload_blocked = False
    scalar._has_attacked_once = True
    clocks = _planes(
        tensor_device,
        cooldown=10.0,
        target=7,
        windup=True,
        preload_blocked=False,
        attacked=True,
    )

    scalar.apply_stun(0.5, source_kind="test")
    result = apply_stun_interrupt_(
        clocks,
        status_applied=torch.tensor([[True]], device=tensor_device),
        hit_speed_ms=torch.tensor(
            [[scalar.card_stats.hit_speed]], device=tensor_device
        ),
    )

    assert result.transitioned.cpu().tolist() == [[True]]
    assert result.combat_blocked.cpu().tolist() == [[True]]
    assert clocks.attack_cooldown.item() == scalar.attack_cooldown == 1.2
    assert clocks.target_slot.item() == -1
    assert scalar.target_id is None
    assert clocks.attack_windup_active.item() is scalar._attack_windup_active
    assert clocks.has_attacked_once.item() is scalar._has_attacked_once
    assert clocks.attack_preload_blocked.item() is scalar._attack_preload_blocked


def test_accepted_shorter_stun_still_interrupts_and_river_defers() -> None:
    clocks = _planes(
        "cpu",
        cooldown=10.0,
        target=3,
        windup=True,
        preload_blocked=False,
        attacked=True,
    )
    result = apply_stun_interrupt_(
        clocks,
        status_applied=torch.tensor([[True]]),
        hit_speed_ms=torch.tensor([[1_200]]),
        river_jump_active=torch.tensor([[True]]),
    )
    assert result.transitioned.tolist() == [[False]]
    assert result.combat_blocked.tolist() == [[True]]
    assert clocks.attack_cooldown.item() == 10.0
    assert clocks.target_slot.item() == 3

    result = apply_stun_interrupt_(
        clocks,
        status_applied=torch.tensor([[True]]),
        hit_speed_ms=torch.tensor([[1_200]]),
    )
    assert result.transitioned.tolist() == [[True]]
    assert clocks.attack_cooldown.item() == 1.2

    retained = _planes(
        "cpu",
        cooldown=0.35,
        target=4,
        windup=True,
        preload_blocked=False,
        attacked=True,
    )
    apply_stun_interrupt_(
        retained,
        status_applied=torch.tensor([[True]]),
        hit_speed_ms=torch.tensor([[1_200]]),
        load_first_hit=True,
        reset_load_first_hit_when_zapped=False,
    )
    assert retained.attack_cooldown.item() == 0.35
    assert retained.target_slot.item() == -1


def test_projectile_knockback_interrupt_and_next_combat_block_match_scalar(
    tensor_device: str,
) -> None:
    battle, scalar = _knight()
    scalar.attack_cooldown = 0.2
    scalar.target_id = 99
    scalar._attack_windup_active = True
    scalar._attack_preload_blocked = False
    scalar._has_attacked_once = True
    scalar.last_attack_time = 4.0
    clocks = _planes(
        tensor_device,
        cooldown=0.2,
        target=5,
        windup=True,
        preload_blocked=False,
        attacked=True,
    )

    assert scalar.begin_knockback(
        Position(10.0, 10.0),
        1_000,
        source_kind="test",
    )
    result = apply_forced_movement_interrupt_(
        clocks,
        movement_started=torch.tensor([[True]], device=tensor_device),
        hit_speed_ms=torch.tensor(
            [[scalar.card_stats.hit_speed]], device=tensor_device
        ),
    )
    scalar.update_combat_component(battle.dt, battle)
    tensor_last_attack = torch.tensor(
        [[4.0]], dtype=torch.float64, device=tensor_device
    )
    tensor_last_attack += torch.where(
        result.combat_blocked,
        torch.zeros_like(tensor_last_attack),
        torch.full_like(tensor_last_attack, battle.dt),
    )

    assert clocks.attack_cooldown.item() == scalar.attack_cooldown == 1.2
    assert clocks.target_slot.item() == 5
    assert scalar.target_id == 99
    assert clocks.attack_preload_blocked.item() is scalar._attack_preload_blocked
    assert clocks.has_attacked_once.item() is scalar._has_attacked_once
    assert tensor_last_attack.item() == scalar.last_attack_time == 4.0


def test_object_phase_spawn_publishes_first_hit_clock_on_birth_tick(
    tensor_device: str,
) -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    spell = SPELL_REGISTRY["GoblinBarrel"]
    assert isinstance(spell, SpawnProjectileSpell)
    stats = troop_from_character_data(
        spell.spawn_character,
        spell.spawn_character_data,
        elixir=0,
        rarity="Common",
    )
    battle._spawn_unit_at_position(
        Position(9.0, 14.0),
        0,
        stats,
        deploy_delay_override=spell.spawn_deploy_delay,
        snap_to_valid=False,
    )
    scalar = battle.entities[1]
    assert isinstance(scalar, Troop)
    scalar.tick_character_object_phase(battle.dt)
    clocks = _planes(
        tensor_device,
        cooldown=0.0,
        target=0,
        windup=True,
        preload_blocked=True,
        attacked=True,
    )

    result = initialize_spawned_attack_clocks_(
        clocks,
        spawned=torch.tensor([[True]], device=tensor_device),
        first_hit_ms=torch.tensor(
            [[stats.first_hit_time]], dtype=torch.int64, device=tensor_device
        ),
    )

    assert result.transitioned.cpu().tolist() == [[True]]
    assert clocks.attack_cooldown.item() == scalar.attack_cooldown == 0.4
    assert scalar.deploy_delay_remaining == pytest.approx(1.05)
    assert clocks.target_slot.item() == -1
    assert not clocks.attack_windup_active.item()
    assert not clocks.attack_preload_blocked.item()
    assert not clocks.has_attacked_once.item()
