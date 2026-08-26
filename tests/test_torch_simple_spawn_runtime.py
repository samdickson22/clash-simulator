from __future__ import annotations

from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_WIDTH, NUM_TILES
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from clasher.torch_sim.simple_spawn_blueprints import FastSpawnBlueprintCatalog


def _runtime(
    root_name: str,
    *,
    device_name: str,
    max_entities: int,
    max_payload_containers: int = 32,
) -> tuple[SimpleGymRuntime, FastSpawnBlueprintCatalog, int]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    loader = BattleState().card_loader
    base = TensorCardCatalog.compile(loader, [root_name], device=device)
    blueprints = FastSpawnBlueprintCatalog.compile(loader, base)
    root = blueprints.cards.name_to_id[root_name]
    decks = torch.full((1, 2, 8), root, dtype=torch.int64, device=device)
    tower_spec = FastTowerSpec(
        card_id=torch.zeros((2, 3), dtype=torch.int64, device=device),
        x_units=torch.tensor(
            [[3_500, 14_500, 9_000], [3_500, 14_500, 9_000]], device=device
        ),
        y_units=torch.tensor(
            [[6_500, 6_500, 2_500], [25_500, 25_500, 29_500]], device=device
        ),
        hitpoints=torch.tensor(
            [[20_000.0, 20_000.0, 30_000.0], [20_000.0, 20_000.0, 30_000.0]],
            device=device,
        ),
        damage=torch.zeros((2, 3), device=device),
        range_units=torch.full((2, 3), 7_500, device=device),
        sight_range_units=torch.full((2, 3), 9_500, device=device),
        hit_cooldown_ticks=torch.full((2, 3), 16, dtype=torch.int32, device=device),
    )
    entity_lookup = torch.zeros(
        (2, blueprints.fast_cards.size), dtype=torch.int64, device=device
    )
    hand_lookup = torch.zeros(
        blueprints.fast_cards.size, dtype=torch.int64, device=device
    )
    public_names = set(base.names[1:])
    for card_id, visible_name in enumerate(blueprints.visible_names):
        if not visible_name:
            continue
        token = 1_000 + card_id
        kind = int(blueprints.fast_cards.kind[card_id])
        if kind >= 0:
            entity_lookup[kind, card_id] = token
        if visible_name in public_names:
            hand_lookup[card_id] = 2_000 + card_id
    runtime = SimpleGymRuntime(
        decks,
        blueprints.fast_cards,
        tower_spec,
        FastMatchRules(regulation_ticks=2_000, tiebreak_ticks=3_000),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        max_entities=max_entities,
        max_payload_containers=max_payload_containers,
        starting_elixir=10.0,
        spawn_blueprints=blueprints,
    )
    return runtime, blueprints, root


def _slot_zero_action(
    runtime: SimpleGymRuntime, *, tile_x: int, tile_y: int
) -> torch.Tensor:
    action = tile_y * BOARD_WIDTH + tile_x
    return torch.tensor(
        [[action, NO_OP_ACTION]], dtype=torch.int64, device=runtime.device
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
@pytest.mark.parametrize(
    ("root_name", "child_name", "count", "radius", "hp", "damage", "deploy"),
    (
        ("BattleRam", "Barbarian", 2, 600, 691.0, 192.0, 20),
        ("LavaHound", "LavaPups", 6, 2_500, 215.0, 81.0, 0),
    ),
)
def test_full_runtime_death_spawns_expanded_typed_children(
    device_name: str,
    root_name: str,
    child_name: str,
    count: int,
    radius: int,
    hp: float,
    damage: float,
    deploy: int,
) -> None:
    runtime, blueprints, root = _runtime(
        root_name, device_name=device_name, max_entities=13
    )
    action = _slot_zero_action(runtime, tile_x=8, tile_y=14)
    deployed = runtime.step_tick(action)
    assert deployed.action_success.tolist() == [[True, True]]
    assert int(runtime.state.card_id[0, 6]) == root
    parent_x = int(runtime.state.x_units[0, 6])
    parent_y = int(runtime.state.y_units[0, 6])
    assert int(runtime.state.stable_id[0, 6]) == 7
    runtime.state.hp[0, 6] = 0.0

    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)
    result = runtime.step_tick(noop)
    child_id = next(
        card_id
        for card_id, name in enumerate(blueprints.visible_names)
        if name == child_name and card_id not in {root}
    )
    children = runtime.state.active & (runtime.state.card_id == child_id)
    assert int(children.sum()) == count
    assert runtime.state.stable_id[children].tolist() == list(range(8, 8 + count))
    torch.testing.assert_close(
        runtime.state.hp[children], torch.full((count,), hp, device=runtime.device)
    )
    torch.testing.assert_close(
        runtime.state.damage[children],
        torch.full((count,), damage, device=runtime.device),
    )
    assert runtime.state.deploy_ticks[children].tolist() == [deploy] * count
    dx = runtime.state.x_units[children].to(torch.float32) - parent_x
    dy = runtime.state.y_units[children].to(torch.float32) - parent_y
    distance = torch.sqrt(dx.square() + dy.square())
    torch.testing.assert_close(
        distance,
        torch.full_like(distance, float(radius)),
        atol=1.0,
        rtol=0.0,
    )
    assert not bool(result.lifecycle.capacity_rejected.any())

    expected_token = int(runtime.projector.inputs.entity_token_lookup[0, child_id])
    actor_ids = result.observation.actor.entity_ids[0, 0]
    actor_mask = result.observation.actor.entity_mask[0, 0]
    assert (actor_ids[actor_mask] == expected_token).sum().item() == count
    # Synthetic child rows are typed entity identities, never hand identities.
    assert int(runtime.projector.inputs.hand_token_lookup[child_id]) == 0
    assert not bool((result.observation.actor.hand_ids == expected_token).any())


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_full_runtime_death_spawn_reports_bounded_capacity(device_name: str) -> None:
    runtime, blueprints, _ = _runtime(
        "BattleRam", device_name=device_name, max_entities=7
    )
    runtime.step_tick(_slot_zero_action(runtime, tile_x=8, tile_y=14))
    runtime.state.hp[0, 6] = 0.0
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)
    result = runtime.step_tick(noop)
    child_id = next(
        index
        for index, name in enumerate(blueprints.visible_names)
        if name == "Barbarian"
    )
    assert int((runtime.state.active & (runtime.state.card_id == child_id)).sum()) == 1
    assert bool(result.lifecycle.capacity_rejected[0, 6])
    assert int(result.lifecycle.capacity_rejected_count[0, 6]) == 1


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_full_runtime_goblin_barrel_impact_spawns_typed_goblins_deterministically(
    device_name: str,
) -> None:
    first, first_blueprints, root = _runtime(
        "GoblinBarrel", device_name=device_name, max_entities=12
    )
    replay, replay_blueprints, replay_root = _runtime(
        "GoblinBarrel", device_name=device_name, max_entities=12
    )
    assert root == replay_root
    assert first_blueprints.cards.names == replay_blueprints.cards.names
    action = _slot_zero_action(first, tile_x=9, tile_y=16)
    first_result = first.step_tick(action)
    replay_result = replay.step_tick(action.clone())
    assert first_result.action_success.tolist() == [[True, True]]
    assert bool(first_result.effect_allocation.projectile[0, 0])
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=first.device)
    for _ in range(80):
        first_result = first.step_tick(noop)
        replay_result = replay.step_tick(noop)
        if first_result.spawn_allocation is not None and bool(
            first_result.spawn_allocation.accepted.any()
        ):
            break
    else:
        raise AssertionError("Goblin Barrel did not impact within its travel budget")

    assert first_result.spawn_allocation is not None
    assert replay_result.spawn_allocation is not None
    assert (
        first_result.spawn_allocation.accepted.tolist()
        == replay_result.spawn_allocation.accepted.tolist()
    )
    assert int(first_result.spawn_allocation.spawned_mask.sum()) == 3
    goblin = next(
        index
        for index, name in enumerate(first_blueprints.visible_names)
        if name == "Goblin"
    )
    children = first.state.active & (first.state.card_id == goblin)
    assert int(children.sum()) == 3
    assert first.state.stable_id[children].tolist() == [7, 8, 9]
    torch.testing.assert_close(
        first.state.hp[children], torch.full((3,), 202.0, device=first.device)
    )
    torch.testing.assert_close(
        first.state.damage[children], torch.full((3,), 120.0, device=first.device)
    )
    assert first.state.deploy_ticks[children].tolist() == [22, 22, 22]
    expected_token = int(first.projector.inputs.entity_token_lookup[0, goblin])
    visible_ids = first_result.observation.actor.entity_ids[0, 0][
        first_result.observation.actor.entity_mask[0, 0]
    ]
    assert (visible_ids == expected_token).sum().item() == 3
    assert int(first.projector.inputs.hand_token_lookup[goblin]) == 0

    for descriptor in fields(first.state):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(first.state, descriptor.name),
                getattr(replay.state, descriptor.name),
            )
    for descriptor in fields(first.effects):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(first.effects, descriptor.name),
                getattr(replay.effects, descriptor.name),
            )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_impact_spawn_capacity_is_masked_before_spending_card(device_name: str) -> None:
    runtime, _, _ = _runtime("GoblinBarrel", device_name=device_name, max_entities=8)
    observation = runtime.observe()
    slot_zero = observation.legal_mask[0, 0, :NUM_TILES]
    assert not bool(slot_zero.any())
    action = _slot_zero_action(runtime, tile_x=9, tile_y=16)
    before_hand = runtime.action_state.hand_ids.clone()
    before_elixir = runtime.action_state.elixir.clone()
    result = runtime.step_tick(action)
    assert result.action_success.tolist() == [[False, True]]
    assert torch.equal(runtime.action_state.hand_ids, before_hand)
    # One native refill tick may advance elixir, but no card cost is spent.
    assert bool((runtime.action_state.elixir >= before_elixir).all())
    assert not bool(runtime.effects.active.any())


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_incomplete_spawn_blueprint_root_remains_illegal(device_name: str) -> None:
    runtime, blueprints, root = _runtime(
        "Golem", device_name=device_name, max_entities=16
    )
    assert bool(blueprints.root_payload_required[root])
    assert not bool(blueprints.root_payload_supported[root])
    assert not bool(blueprints.fast_cards.training_supported[root])
    assert not bool(runtime.observe().legal_mask[0, 0, :NO_OP_ACTION].any())


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
@pytest.mark.parametrize(
    ("root_name", "lifetime_ticks", "damage", "radius_units"),
    (
        ("Balloon", 60, 240.0, 3_000),
        ("BombTower", 60, 222.0, 3_000),
        ("SkeletonBarrel", 12, 145.0, 2_000),
    ),
)
def test_full_runtime_delayed_payload_damage_nested_spawn_and_replay(
    device_name: str,
    root_name: str,
    lifetime_ticks: int,
    damage: float,
    radius_units: int,
) -> None:
    first, blueprints, root = _runtime(
        root_name,
        device_name=device_name,
        max_entities=20,
    )
    replay, replay_blueprints, replay_root = _runtime(
        root_name,
        device_name=device_name,
        max_entities=20,
    )
    assert root == replay_root
    assert blueprints.cards.names == replay_blueprints.cards.names
    action = _slot_zero_action(first, tile_x=8, tile_y=14)
    first_deploy = first.step_tick(action)
    replay_deploy = replay.step_tick(action.clone())
    assert first_deploy.action_success.tolist() == [[True, True]]
    assert replay_deploy.action_success.tolist() == [[True, True]]

    enemy_tower_slot = 3
    tower_x = int(first.state.x_units[0, enemy_tower_slot])
    tower_y = int(first.state.y_units[0, enemy_tower_slot])
    for runtime in (first, replay):
        parent = runtime.state.active & (runtime.state.card_id == root)
        parent[:, :6] = False
        assert int(parent.sum()) == 1
        slot = int(parent.to(torch.int8).argmax(dim=1)[0])
        runtime.state.x_units[0, slot] = tower_x
        runtime.state.y_units[0, slot] = tower_y
        runtime.state.hp[0, slot] = 0.0

    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=first.device)
    first_death = first.step_tick(noop)
    replay_death = replay.step_tick(noop)
    assert first_death.payload_container_allocation is not None
    assert replay_death.payload_container_allocation is not None
    assert first_death.payload_container_allocation.accepted[0, 0]
    assert replay_death.payload_container_allocation.accepted[0, 0]
    assert int(
        first.payload_containers.lifetime_ticks[first.payload_containers.active]
    ) == (lifetime_ticks)
    assert int(
        first.payload_containers.effect_radius_units[first.payload_containers.active]
    ) == (radius_units)
    assert float(
        first.payload_containers.effect_damage[first.payload_containers.active]
    ) == (damage)
    # The delayed object never occupies or projects through the combat pool.
    assert not bool(
        (first.state.active[:, 6:] & (first.state.card_id[:, 6:] == root)).any()
    )
    root_kind = int(first.action_kernel.catalog.kind[root])
    root_token = int(first.projector.inputs.entity_token_lookup[root_kind, root])
    visible = first_death.observation.actor.entity_ids[
        first_death.observation.actor.entity_mask
    ]
    assert not bool((visible == root_token).any())

    tower_hp = float(first.state.hp[0, enemy_tower_slot])
    for _ in range(lifetime_ticks - 1):
        first_step = first.step_tick(noop)
        replay_step = replay.step_tick(noop)
        assert not bool(first_step.payloads.effect_commands.ready.any())
        assert not bool(replay_step.payloads.effect_commands.ready.any())
        assert float(first.state.hp[0, enemy_tower_slot]) == tower_hp

    first_step = first.step_tick(noop)
    replay_step = replay.step_tick(noop)
    assert first_step.payloads.effect_commands.ready[0, 0]
    assert replay_step.payloads.effect_commands.ready[0, 0]
    assert first_step.payload_effect_allocation.accepted[0, 0]
    assert replay_step.payload_effect_allocation.accepted[0, 0]
    assert float(first.state.hp[0, enemy_tower_slot]) == pytest.approx(
        tower_hp - damage
    )
    assert float(replay.state.hp[0, enemy_tower_slot]) == pytest.approx(
        tower_hp - damage
    )
    assert not bool(first.payload_containers.active.any())

    if root_name == "SkeletonBarrel":
        assert first_step.payload_spawn_allocation is not None
        assert first_step.payload_spawn_allocation.accepted[0, 0]
        skeleton = next(
            index
            for index, name in enumerate(blueprints.visible_names)
            if name == "Skeleton"
        )
        children = first.state.active & (first.state.card_id == skeleton)
        assert int(children.sum()) == 7
        assert first.state.deploy_ticks[children].tolist() == [10] * 7
        expected_token = int(first.projector.inputs.entity_token_lookup[0, skeleton])
        visible_ids = first_step.observation.actor.entity_ids[0, 0][
            first_step.observation.actor.entity_mask[0, 0]
        ]
        assert int((visible_ids == expected_token).sum()) == 7
        assert int(first.projector.inputs.hand_token_lookup[skeleton]) == 0
    else:
        assert first_step.payload_spawn_allocation is not None
        assert not bool(first_step.payload_spawn_allocation.accepted.any())

    for owner_name in ("state", "payload_containers"):
        left = getattr(first, owner_name)
        right = getattr(replay, owner_name)
        for descriptor in fields(left):
            if descriptor.name != "device":
                assert torch.equal(
                    getattr(left, descriptor.name),
                    getattr(right, descriptor.name),
                )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_full_runtime_payload_container_capacity_is_explicit_and_stable(
    device_name: str,
) -> None:
    runtime, _, root = _runtime(
        "Balloon",
        device_name=device_name,
        max_entities=12,
        max_payload_containers=1,
    )
    runtime.step_tick(_slot_zero_action(runtime, tile_x=8, tile_y=14))
    first_slot = 6
    second_slot = 7
    for descriptor in fields(runtime.state):
        value = getattr(runtime.state, descriptor.name)
        if (
            descriptor.name != "device"
            and isinstance(value, torch.Tensor)
            and value.ndim == 2
            and value.shape[1] == runtime.state.max_entities
        ):
            value[0, second_slot] = value[0, first_slot]
    runtime.state.active[0, second_slot] = True
    runtime.state.stable_id[0, second_slot] = 8
    runtime.state.next_stable_id[0] = 9
    runtime.state.hp[0, [first_slot, second_slot]] = 0.0
    assert runtime.state.card_id[0, [first_slot, second_slot]].tolist() == [
        root,
        root,
    ]

    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)
    result = runtime.step_tick(noop)
    assert result.payload_container_allocation is not None
    allocation = result.payload_container_allocation
    assert allocation.accepted[0, :2].tolist() == [True, False]
    assert allocation.capacity_rejected[0, :2].tolist() == [False, True]
    assert allocation.capacity_rejected_count.tolist() == [1]
    assert runtime.payload_containers.active.tolist() == [[True]]
    # Lower source stable ID wins independently of the reusable entity slots.
    assert runtime.payload_containers.source_id.tolist() == [[7]]
