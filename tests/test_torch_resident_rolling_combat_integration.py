from __future__ import annotations

import copy

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import RollingProjectile
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_workspace import TensorResidentWorkspace
from clasher.torch_sim.runtime_state import RuntimeEventOpcode


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _spawn(
    battle: BattleState,
    name: str,
    entity_id: int,
    player_id: int,
    position: Position,
    *,
    attack_cooldown: float = 0.0,
) -> None:
    assert battle.next_entity_id == entity_id
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    battle._spawn_unit_at_position(
        position,
        player_id,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    entity = battle.entities[entity_id]
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity.attack_cooldown = attack_cooldown


def _bowler_battle(
    *,
    source_order: tuple[str, ...] = ("Bowler",),
    target_name: str = "Knight",
) -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    for entity_id, name in enumerate(source_order, start=1):
        _spawn(battle, name, entity_id, 0, Position(9.0, 10.0))
    target_id = len(source_order) + 1
    _spawn(battle, target_name, target_id, 1, Position(9.0, 14.0))
    target = battle.entities[target_id]
    target.stun_timer = 100.0
    target.attack_cooldown = 100.0
    for entity_id in range(1, target_id):
        battle.entities[entity_id].target_id = target_id
    return battle


def _engine(battles: list[BattleState], device: str) -> TensorResidentEngine:
    return TensorResidentEngine.from_battles(
        battles,
        device=device,
        max_entities=16,
        max_objects=8,
        event_capacity=512,
    )


def _assert_public_state(oracle: BattleState, engine: TensorResidentEngine) -> None:
    core = engine.runtime.battle
    active = engine.runtime.entity_pool.active[0]
    slots = torch.where(active)[0]
    entity_ids = core.entity_id[0, slots].tolist()
    assert entity_ids == list(oracle.entities)
    assert engine.runtime.entity_pool.next_entity_id.item() == oracle.next_entity_id
    assert core.time.item() == oracle.time
    assert core.tick.item() == oracle.tick
    assert core.rng.python_state(0) == oracle.rng.getstate()
    for slot, entity_id in zip(slots.tolist(), entity_ids, strict=True):
        entity = oracle.entities[entity_id]
        assert core.entity_x_units[0, slot].item() == round(entity.position.x * 1_000)
        assert core.entity_y_units[0, slot].item() == round(entity.position.y * 1_000)
        assert core.entity_hp[0, slot].item() == entity.hitpoints
        assert core.entity_hp_integer_kind[0, slot].item() is (
            type(entity.hitpoints) is int
        )


def test_bowler_attack_to_terminal_matches_scalar(tensor_device: str) -> None:
    source = _bowler_battle(target_name="Prince")
    oracle = copy.deepcopy(source)
    engine = _engine([source], tensor_device)
    order = torch.tensor([[0, 1]], device=engine.device)

    bowler_card = engine.runtime.battle.card_to_id["Bowler"]
    assert engine.rolling_combat.catalog.supported[bowler_card]
    assert engine.preflight().supported.tolist() == [True]
    launched_id = 0

    for _ in range(70):
        oracle.step_logic_ticks(1)
        result = engine.step(player_order=order)

        assert result.committed.tolist() == [True]
        _assert_public_state(oracle, engine)
        scalar_rollers = [
            entity
            for entity in oracle.entities.values()
            if isinstance(entity, RollingProjectile)
        ]
        tensor_rollers = engine.rolling_combat.state.active[0]
        assert tensor_rollers.sum().item() == len(scalar_rollers)
        assert not engine.objects.objects.allocated.any()
        if result.rolling_combat_materialization.selected_count.item():
            assert result.rolling_combat_materialization.selected_count.item() == 1
            launched_id = int(
                engine.rolling_combat.state.entity_id[0, tensor_rollers].item()
            )
        if scalar_rollers:
            scalar = scalar_rollers[0]
            assert engine.rolling_combat.state.entity_id[0, tensor_rollers].item() == (
                scalar.id
            )
            assert engine.rolling_combat.state.x_units[0, tensor_rollers].item() == (
                round(scalar.position.x * 1_000)
            )
            assert engine.rolling_combat.state.y_units[0, tensor_rollers].item() == (
                round(scalar.position.y * 1_000)
            )
            assert engine.rolling_combat.state.distance_units[
                0, tensor_rollers
            ].item() == round(scalar.distance_traveled * 1_000)
        elif launched_id:
            break
    else:
        raise AssertionError("Bowler projectile did not terminate")

    count = int(engine.runtime.events.count[0])
    spawn = engine.runtime.events.opcode[0, :count] == int(RuntimeEventOpcode.SPAWN)
    assert engine.runtime.events.source_id[0, :count][spawn].tolist() == [1]
    assert engine.runtime.events.target_id[0, :count][spawn].tolist() == [launched_id]
    assert engine.runtime.events.payload[0, :count][spawn].tolist() == [bowler_card]


def test_rolling_launch_capacity_failure_is_row_atomic(tensor_device: str) -> None:
    first = _bowler_battle()
    second = copy.deepcopy(first)
    engine = _engine([first, second], tensor_device)
    engine.runtime.events.count[0] = engine.runtime.events.capacity
    before_time = engine.runtime.battle.time.clone()
    before_ids = engine.runtime.battle.entity_id.clone()
    before_next_id = engine.runtime.entity_pool.next_entity_id.clone()
    before_combat = engine.combat.attack_cooldown.clone()
    before_rng = engine.runtime.battle.rng.python_state(0)

    result = engine.step(
        player_order=torch.tensor([[0, 1], [0, 1]], device=engine.device)
    )

    assert result.committed.tolist() == [False, True]
    assert engine.runtime.battle.time[0] == before_time[0]
    assert torch.equal(engine.runtime.battle.entity_id[0], before_ids[0])
    assert engine.runtime.entity_pool.next_entity_id[0] == before_next_id[0]
    assert torch.equal(engine.combat.attack_cooldown[0], before_combat[0])
    assert engine.runtime.battle.rng.python_state(0) == before_rng
    assert not engine.rolling_combat.state.active[0].any()
    assert not engine.objects.objects.allocated[0].any()

    assert engine.rolling_combat.state.active[1].sum().item() == 1
    assert not engine.objects.objects.allocated[1].any()
    assert engine.runtime.entity_pool.next_entity_id[1].item() == 4


def test_bowler_knockback_begins_on_tick_after_object_hit(tensor_device: str) -> None:
    source = _bowler_battle()
    oracle = copy.deepcopy(source)
    engine = _engine([source], tensor_device)
    order = torch.tensor([[0, 1]], device=engine.device)
    target_slot = 1

    for _ in range(30):
        oracle.step_logic_ticks(1)
        result = engine.step(player_order=order)
        assert result.committed.tolist() == [True]
        if result.rolling_combat.hit[0, target_slot]:
            assert oracle.entities[2].forced_movement_active
            assert engine.projectile_bridge.knockback_active[0, target_slot]
            assert engine.runtime.battle.entity_y_units[0, target_slot].item() == 14_000
            assert round(oracle.entities[2].position.y * 1_000) == 14_000
            break
    else:
        raise AssertionError("Bowler projectile did not hit the target")

    oracle.step_logic_ticks(1)
    result = engine.step(player_order=order)
    assert result.committed.tolist() == [True]
    assert engine.runtime.battle.entity_x_units[0, target_slot].item() == round(
        oracle.entities[2].position.x * 1_000
    )
    assert engine.runtime.battle.entity_y_units[0, target_slot].item() == round(
        oracle.entities[2].position.y * 1_000
    )
    assert engine.runtime.battle.entity_y_units[0, target_slot].item() > 14_000


def test_workspace_retains_independent_rolling_state(tensor_device: str) -> None:
    engine = _engine([_bowler_battle()], tensor_device)
    workspace = TensorResidentWorkspace(engine)
    scratch_pointer = workspace.scratch.rolling_combat.state.active.data_ptr()
    committed_pointer = engine.rolling_combat.state.active.data_ptr()

    result = workspace.step(player_order=torch.tensor([[0, 1]], device=engine.device))

    assert result.committed.tolist() == [True]
    assert engine.rolling_combat.state.active.sum().item() == 1
    assert scratch_pointer == workspace.scratch.rolling_combat.state.active.data_ptr()
    assert scratch_pointer != committed_pointer
    workspace.refresh()
    assert torch.equal(
        workspace.scratch.rolling_combat.state.entity_id,
        engine.rolling_combat.state.entity_id,
    )


@pytest.mark.parametrize(
    ("source_order", "committed"),
    (
        (("Bowler", "Archer"), True),
        (("Archer", "Bowler"), False),
    ),
)
def test_mixed_rolling_and_generic_launches_preserve_global_order_or_rollback(
    tensor_device: str,
    source_order: tuple[str, str],
    committed: bool,
) -> None:
    engine = _engine([_bowler_battle(source_order=source_order)], tensor_device)
    before_ids = engine.runtime.battle.entity_id.clone()
    before_next_id = engine.runtime.entity_pool.next_entity_id.clone()

    result = engine.step(player_order=torch.tensor([[0, 1]], device=engine.device))

    assert result.committed.tolist() == [committed]
    if not committed:
        assert torch.equal(engine.runtime.battle.entity_id, before_ids)
        assert torch.equal(engine.runtime.entity_pool.next_entity_id, before_next_id)
        assert not engine.rolling_combat.state.active.any()
        assert not engine.objects.objects.allocated.any()
        assert engine.runtime.events.count.tolist() == [0]
        return

    assert engine.rolling_combat.state.active.sum().item() == 1
    assert engine.objects.objects.allocated.sum().item() == 1
    assert engine.runtime.entity_pool.next_entity_id.item() == 6
    count = int(engine.runtime.events.count[0])
    created = (
        engine.runtime.events.opcode[0, :count] == int(RuntimeEventOpcode.SPAWN)
    ) | (engine.runtime.events.opcode[0, :count] == int(RuntimeEventOpcode.PROJECTILE))
    assert engine.runtime.events.source_id[0, :count][created].tolist() == [1, 2]
    assert engine.runtime.events.target_id[0, :count][created].tolist() == [4, 5]
