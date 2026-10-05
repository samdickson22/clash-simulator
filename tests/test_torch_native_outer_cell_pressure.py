"""Moving centers may enter outer half-cells without changing spawn margins."""

from types import SimpleNamespace

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.torch_sim.movement import (
    clamp_native_positions,
    target_directed_movement_step,
)
from clasher.torch_sim.movement_adapter import TensorMovementAdapter
from clasher.torch_sim.projectile_bridge import TensorResidentProjectileSpellBridge
from clasher.torch_sim.runtime import TensorTickRuntime
from clasher.torch_sim.runtime_movement import step_runtime_movement_
from clasher.unit_traits import unit_mass


@pytest.mark.parametrize("width,height", [(18_000, 32_000), (10_000, 20_000)])
def test_moving_center_bounds_use_last_logic_unit(width, height):
    positions = torch.tensor(
        [[-1, -1], [0, 0], [211, 211], [width - 211, height - 211],
         [width - 1, height - 1], [width, height]],
        dtype=torch.int32,
    )
    expected = positions.to(torch.int64)
    expected[0] = torch.tensor([0, 0])
    expected[-1] = torch.tensor([width - 1, height - 1])
    assert torch.equal(
        clamp_native_positions(
            positions, arena_width_units=width, arena_height_units=height
        ),
        expected,
    )


def test_natural_movement_keeps_outer_cell_pressure_and_unsupported_slots():
    positions = torch.tensor([[17_750, 10_000], [18_100, -100]])
    result = target_directed_movement_step(
        positions,
        torch.tensor([[17_750, 11_000], [17_750, 11_000]]),
        torch.tensor([1, 1]),
        supported=torch.tensor([True, False]),
        external_vector_units=torch.tensor([[39, 0], [39, 0]]),
    )
    assert result.position_units.tolist() == [[17_789, 10_001], [18_100, -100]]
    assert result.movement_vector_units.tolist() == [[0, 1], [0, 0]]


@pytest.mark.parametrize(
    "phase,card,pressure,expected",
    [
        ("collision_only", "Knight", 39, [17_789, 10_000]),
        ("ordinary", "BabyDragon", 150, [17_885, 10_088]),
        ("river_jump", "HogRider", 150, [17_900, 10_160]),
    ],
)
def test_runtime_movement_consumers_preserve_outer_cell_pressure(
    phase, card, pressure, expected
):
    battle = BattleState()
    battle._spawn_troop(Position(17.75, 10), 0, battle.card_loader.get_card(card))
    troop = battle.entities[battle.next_entity_id - 1]
    troop.deploy_delay_remaining = 0
    troop.placement_pending = False
    if phase == "ordinary":
        troop._movement_target_id = next(
            entity.id for entity in battle.entities.values()
            if entity.player_id == 1 and entity.position.x == 14.5
        )
    elif phase == "river_jump":
        troop._river_jump_active = True
        troop._river_jump_target = Position(17.75, 11)
        troop._river_jump_origin = Position(17.75, 10)

    # Exercise the actual scalar-to-tensor adapters, including card mass lookup.
    runtime = TensorTickRuntime.from_battles([battle])
    adapter = TensorMovementAdapter.from_battles([battle])
    slot = adapter.entity_id[0].tolist().index(troop.id)
    expected_mass = round(unit_mass(troop.card_stats) * 1_000)
    assert runtime.mass_milliunits[0, slot].item() == expected_mass
    assert adapter.mass_milliunits[0, slot].item() == expected_mass
    adapter.accumulated_vector_units[0, slot, 0] = pressure
    adapter.accumulated_vector_count[0, slot] = 1

    result = step_runtime_movement_(runtime, adapter)

    assert result.supported_batch.tolist() == [True], result.unsupported_reasons
    assert getattr(result, phase + "_moved")[0, slot].item()
    assert adapter.position_units[0, slot].tolist() == expected
    assert runtime.core.entity_x_units[0, slot].item() == expected[0]
    assert runtime.core.entity_y_units[0, slot].item() == expected[1]
    assert adapter.accumulated_vector_count[0, slot].item() == 0


@pytest.mark.parametrize(
    "position,target,expected",
    [
        ([17_750, 10_000], [18_750, 10_000], [17_789, 10_000]),
        ([17_990, 10_000], [18_750, 10_000], [17_999, 10_000]),
        ([10, 10], [-1_000, 10], [0, 10]),
        ([10_000, 31_990], [10_000, 33_000], [10_000, 31_999]),
    ],
)
def test_projectile_knockback_uses_movement_bounds(position, target, expected):
    # This phase consumes only these retained tensors; no projectile launch is needed.
    active = torch.tensor([[True, False]])
    positions = torch.tensor([[position, [17_750, 10_000]]], dtype=torch.int32)
    state = SimpleNamespace(
        knockback_active=active.clone(),
        knockback_entity_id=torch.tensor([[1, 2]]),
        knockback_target_units=torch.tensor([[target, target]]),
        knockback_velocity_work=torch.tensor([[64, 64]], dtype=torch.int32),
    )
    runtime = SimpleNamespace(
        entity_pool=SimpleNamespace(active=torch.ones_like(active)),
        battle=SimpleNamespace(
            entity_id=torch.tensor([[1, 2]]),
            entity_active=torch.ones_like(active),
            entity_x_units=positions[..., 0].clone(),
            entity_y_units=positions[..., 1].clone(),
        ),
    )
    TensorResidentProjectileSpellBridge._advance_knockback_(state, runtime, active)
    assert runtime.battle.entity_x_units.tolist() == [[expected[0], 17_750]]
    assert runtime.battle.entity_y_units.tolist() == [[expected[1], 10_000]]
