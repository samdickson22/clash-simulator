from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_WIDTH
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.policy_validation import PUBLIC_ACTION_MASK_CONTRACT_V2
from clasher.torch_sim.simple_adapter import SimpleGymAdapter
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_effects import FAST_EFFECT_AREA, FAST_STATUS_STUN
from clasher.torch_sim.simple_navigation import (
    FAST_ROUTE_CROSS_BRIDGE,
    FAST_ROUTE_DIRECT,
)
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime, _same_device


def _runtime_for_cards(
    device_name: str,
    card_names: tuple[str, ...],
    *,
    max_entities: int = 12,
) -> tuple[SimpleGymRuntime, dict[str, int]]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    full = TensorCardCatalog.compile(
        BattleState().card_loader, card_names, device=device
    )
    catalog = FastCardCatalog.from_tensor_catalog(full)
    ids = {name: full.name_to_id[name] for name in card_names}
    knight = ids["Knight"]
    decks = torch.full((1, 2, 8), knight, dtype=torch.int64, device=device)
    tower_spec = FastTowerSpec(
        card_id=torch.full((2, 3), knight, dtype=torch.int64, device=device),
        x_units=torch.tensor(
            [[3_500, 14_500, 9_000], [3_500, 14_500, 9_000]], device=device
        ),
        y_units=torch.tensor(
            [[6_500, 6_500, 2_500], [25_500, 25_500, 29_500]], device=device
        ),
        hitpoints=torch.tensor(
            [[2_000.0, 2_000.0, 3_000.0], [2_000.0, 2_000.0, 3_000.0]],
            device=device,
        ),
        damage=torch.zeros((2, 3), device=device),
        range_units=torch.full((2, 3), 7_500, device=device),
        sight_range_units=torch.full((2, 3), 9_500, device=device),
        hit_cooldown_ticks=torch.full((2, 3), 16, dtype=torch.int32, device=device),
    )
    entity_lookup = torch.zeros((2, catalog.size), dtype=torch.int64, device=device)
    for offset, card_id in enumerate(ids.values(), start=1):
        entity_lookup[0, card_id] = 100 + offset
        entity_lookup[1, card_id] = 200 + offset
    hand_lookup = torch.arange(catalog.size, dtype=torch.int64, device=device) + 100
    return (
        SimpleGymRuntime(
            decks,
            catalog,
            tower_spec,
            FastMatchRules(regulation_ticks=200, tiebreak_ticks=400),
            entity_token_lookup=entity_lookup,
            hand_token_lookup=hand_lookup,
            max_entities=max_entities,
        ),
        ids,
    )


def _runtime(
    device_name: str, *, max_entities: int = 12
) -> tuple[SimpleGymRuntime, int]:
    runtime, ids = _runtime_for_cards(
        device_name,
        ("Knight",),
        max_entities=max_entities,
    )
    return runtime, ids["Knight"]


def _seed_runtime_troop(
    runtime: SimpleGymRuntime,
    *,
    slot: int,
    stable_id: int,
    owner: int,
    card_id: int,
    x_units: int,
    y_units: int,
) -> None:
    state = runtime.state
    catalog = runtime.action_kernel.catalog
    state.active[0, slot] = True
    state.stable_id[0, slot] = stable_id
    state.next_stable_id[0] = max(int(state.next_stable_id[0]), stable_id + 1)
    state.owner[0, slot] = owner
    state.card_id[0, slot] = card_id
    state.kind[0, slot] = catalog.kind[card_id]
    state.x_units[0, slot] = x_units
    state.y_units[0, slot] = y_units
    state.hp[0, slot] = catalog.hitpoints[card_id]
    state.max_hp[0, slot] = catalog.hitpoints[card_id]
    state.target_id[0, slot] = 0
    state.damage[0, slot] = catalog.damage[card_id]
    state.range_units[0, slot] = catalog.range_units[card_id]
    state.sight_range_units[0, slot] = catalog.sight_range_units[card_id]
    state.speed_units_per_tick[0, slot] = catalog.speed_units_per_tick[card_id]
    state.hit_cooldown_ticks[0, slot] = catalog.hit_cooldown_ticks[card_id]
    state.deploy_ticks[0, slot] = 0
    state.cooldown_ticks[0, slot] = 0


def _knight_actions(device: torch.device) -> torch.Tensor:
    tile = 14 * BOARD_WIDTH + 8
    return torch.tensor([[tile, tile]], dtype=torch.int64, device=device)


def _far_knight_actions(device: torch.device) -> torch.Tensor:
    tile = 7 * BOARD_WIDTH + 8
    return torch.tensor([[tile, tile]], dtype=torch.int64, device=device)


def test_device_aliases_match_the_same_accelerator() -> None:
    assert _same_device(torch.device("cuda"), torch.device("cuda:0"))
    assert _same_device(torch.device("cpu"), torch.device("cpu"))
    assert not _same_device(torch.device("cuda:0"), torch.device("cuda:1"))
    assert not _same_device(torch.device("cpu"), torch.device("cuda"))


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_runtime_knight_action_moves_hits_and_replays_deterministically(
    device_name: str,
) -> None:
    first, knight = _runtime(device_name)
    replay, _ = _runtime(device_name)
    action = _knight_actions(first.device)

    initial = first.step_tick(action)
    replay_initial = replay.step_tick(action)
    assert initial.action_success.tolist() == [[True, True]]
    assert replay_initial.action_success.tolist() == [[True, True]]
    assert first.state.card_id[0, 6:8].tolist() == [knight, knight]
    initial_positions = torch.stack(
        (first.state.x_units[0, 6:8], first.state.y_units[0, 6:8]),
        dim=1,
    ).clone()

    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=first.device)
    for _ in range(260):
        first_result = first.step_tick(noop)
        replay_result = replay.step_tick(noop)

    final_positions = torch.stack(
        (first.state.x_units[0, 6:8], first.state.y_units[0, 6:8]),
        dim=1,
    )
    assert not torch.equal(final_positions, initial_positions)
    assert bool((first.state.hp < first.state.max_hp).any())
    torch.testing.assert_close(first_result.reward, replay_result.reward)
    torch.testing.assert_close(
        first_result.observation.actor.entity_features,
        replay_result.observation.actor.entity_features,
    )
    for descriptor in fields(first.state):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(first.state, descriptor.name),
                getattr(replay.state, descriptor.name),
            )
    for descriptor in fields(first.combat.navigation.state):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(first.combat.navigation.state, descriptor.name),
                getattr(replay.combat.navigation.state, descriptor.name),
            )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_runtime_ground_crosses_bridge_while_air_moves_direct(
    device_name: str,
) -> None:
    runtime, ids = _runtime_for_cards(
        device_name,
        ("Knight", "BabyDragon"),
    )
    _seed_runtime_troop(
        runtime,
        slot=6,
        stable_id=7,
        owner=0,
        card_id=ids["Knight"],
        x_units=3_500,
        y_units=14_500,
    )
    _seed_runtime_troop(
        runtime,
        slot=7,
        stable_id=8,
        owner=0,
        card_id=ids["BabyDragon"],
        x_units=9_000,
        y_units=14_500,
    )
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)

    runtime.step_tick(noop)

    routes = runtime.combat.navigation.state
    assert int(routes.route_phase[0, 6]) == FAST_ROUTE_CROSS_BRIDGE
    assert int(routes.route_phase[0, 7]) == FAST_ROUTE_DIRECT
    assert int(routes.bridge_index[0, 6]) == 0
    assert int(routes.bridge_index[0, 7]) == -1
    assert int(runtime.state.x_units[0, 6]) == 3_500
    assert int(runtime.state.y_units[0, 6]) > 14_500
    assert int(runtime.state.x_units[0, 7]) < 9_000
    assert int(runtime.state.y_units[0, 7]) > 14_500

    for _ in range(50):
        runtime.step_tick(noop)
    assert int(runtime.state.y_units[0, 6]) > 17_500
    assert int(routes.route_phase[0, 6]) == FAST_ROUTE_DIRECT


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_runtime_reused_entity_slot_replans_by_stable_identity(
    device_name: str,
) -> None:
    runtime, knight = _runtime(device_name)
    _seed_runtime_troop(
        runtime,
        slot=6,
        stable_id=7,
        owner=0,
        card_id=knight,
        x_units=3_500,
        y_units=8_000,
    )
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)
    runtime.step_tick(noop)
    routes = runtime.combat.navigation.state
    assert int(routes.mover_stable_id[0, 6]) == 7
    assert int(routes.bridge_index[0, 6]) == 0

    runtime.state.active[0, 6] = False
    runtime.state.hp[0, 6] = 0
    _seed_runtime_troop(
        runtime,
        slot=6,
        stable_id=8,
        owner=0,
        card_id=knight,
        x_units=14_500,
        y_units=8_000,
    )
    runtime.step_tick(noop)

    assert int(routes.mover_stable_id[0, 6]) == 8
    assert int(routes.bridge_index[0, 6]) == 1


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_far_knights_navigate_before_sight_then_deal_damage(
    device_name: str,
) -> None:
    runtime, _ = _runtime(device_name)
    deployed = runtime.step_tick(_far_knight_actions(runtime.device))
    assert deployed.action_success.tolist() == [[True, True]]
    initial_positions = runtime.state.y_units[0, 6:8].clone()
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)

    # Deployment completes while the troops are still much farther apart than
    # Knight sight. Both then receive enemy Crown navigation identities.
    for _ in range(22):
        result = runtime.step_tick(noop)
    assert not torch.equal(runtime.state.y_units[0, 6:8], initial_positions)
    assert runtime.state.target_id[0, 6:8].gt(0).all()
    assert not result.effects.impacted.any()

    for _ in range(310):
        result = runtime.step_tick(noop)
        if bool((runtime.state.hp < runtime.state.max_hp).any()):
            break

    assert bool((runtime.state.hp < runtime.state.max_hp).any())


def test_dead_tower_slot_is_never_reused_by_deployment() -> None:
    runtime, knight = _runtime("cpu", max_entities=7)
    runtime.state.hp[0, 0] = 0.0
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64)
    runtime.step_tick(noop)
    assert not bool(runtime.state.active[0, 0])

    action = _knight_actions(runtime.device)
    action[0, 1] = NO_OP_ACTION
    deployed = runtime.step_tick(action)
    assert deployed.action_success.tolist() == [[True, True]]
    assert not bool(runtime.state.active[0, 0])
    assert int(runtime.state.card_id[0, 0]) == knight
    assert bool(runtime.state.active[0, 6])
    assert int(runtime.state.card_id[0, 6]) == knight

    # A full ordinary pool fails placement masks closed without hiding no-op.
    full_mask = runtime.observe().legal_mask
    assert not full_mask[:, :, :NO_OP_ACTION].any()
    assert full_mask[:, :, NO_OP_ACTION].all()


def test_one_free_slot_prefers_player_zero_and_rolls_back_player_one() -> None:
    runtime, _ = _runtime("cpu", max_entities=7)
    before_hand = runtime.action_state.hand_ids.clone()
    before_cycle = runtime.action_state.cycle_ids.clone()
    before_head = runtime.action_state.cycle_head.clone()
    before_elixir = runtime.action_state.elixir.clone()

    result = runtime.step_tick(_knight_actions(runtime.device))

    assert result.action_success.tolist() == [[True, False]]
    assert int(runtime.state.owner[0, 6]) == 0
    assert not torch.equal(runtime.action_state.cycle_head[0, 0], before_head[0, 0])
    assert runtime.action_state.elixir[0, 0] < before_elixir[0, 0]
    assert torch.equal(runtime.action_state.hand_ids[0, 1], before_hand[0, 1])
    assert torch.equal(runtime.action_state.cycle_ids[0, 1], before_cycle[0, 1])
    assert torch.equal(runtime.action_state.cycle_head[0, 1], before_head[0, 1])
    torch.testing.assert_close(
        runtime.action_state.elixir[0, 1], before_elixir[0, 1] + 0.05 / 2.8
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_stunned_knight_is_targetable_but_does_not_move_or_cool_down(
    device_name: str,
) -> None:
    frozen, _ = _runtime(device_name)
    ordinary, _ = _runtime(device_name)
    frozen.step_tick(_knight_actions(frozen.device))
    ordinary.step_tick(_knight_actions(ordinary.device))
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=frozen.device)
    # Leave both Knights one tick from completing deployment.
    for _ in range(18):
        frozen.step_tick(noop)
        ordinary.step_tick(noop)
    assert int(frozen.state.deploy_ticks[0, 6]) == 1

    frozen.entity_status_kind[0, 6] = FAST_STATUS_STUN
    frozen.entity_status_ticks[0, 6] = 2
    frozen.state.cooldown_ticks[0, 6] = 5
    ordinary.state.cooldown_ticks[0, 6] = 5
    frozen_x = frozen.state.x_units[0, 6].clone()
    frozen_y = frozen.state.y_units[0, 6].clone()
    ordinary_x = ordinary.state.x_units[0, 6].clone()
    ordinary_y = ordinary.state.y_units[0, 6].clone()

    frozen.step_tick(noop)
    ordinary.step_tick(noop)

    assert torch.equal(frozen.state.x_units[0, 6], frozen_x)
    assert torch.equal(frozen.state.y_units[0, 6], frozen_y)
    assert int(frozen.state.cooldown_ticks[0, 6]) == 5
    assert int(frozen.state.target_id[0, 6]) == 0
    # The enemy can still acquire the disabled Knight by its stable identity.
    assert int(frozen.state.target_id[0, 7]) == 7
    assert not (
        torch.equal(ordinary.state.x_units[0, 6], ordinary_x)
        and torch.equal(ordinary.state.y_units[0, 6], ordinary_y)
    )
    assert int(ordinary.state.cooldown_ticks[0, 6]) == 4


def test_runtime_advances_owned_effect_and_status_planes() -> None:
    runtime, _ = _runtime("cpu")
    runtime.step_tick(_knight_actions(runtime.device))
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64)
    for _ in range(18):
        runtime.step_tick(noop)
    knight_slot = 6
    hp_before = runtime.state.hp[0, knight_slot].clone()
    position_before_impact = torch.stack(
        (
            runtime.state.x_units[0, knight_slot],
            runtime.state.y_units[0, knight_slot],
        )
    ).clone()
    runtime.effects.active[0, 0] = True
    runtime.effects.kind[0, 0] = FAST_EFFECT_AREA
    runtime.effects.source_owner[0, 0] = 1
    runtime.effects.x_units[0, 0] = runtime.state.x_units[0, knight_slot]
    runtime.effects.y_units[0, 0] = runtime.state.y_units[0, knight_slot]
    runtime.effects.damage[0, 0] = 50.0
    runtime.effects.radius_units[0, 0] = 1_000
    runtime.effects.status_kind[0, 0] = FAST_STATUS_STUN
    runtime.effects.status_duration_ticks[0, 0] = 3
    runtime.effects.lifetime_ticks[0, 0] = 1

    result = runtime.step_tick(noop)

    assert bool(result.effects.impacted[0, 0])
    assert not bool(runtime.effects.active[0, 0])
    assert not torch.equal(
        torch.stack(
            (
                runtime.state.x_units[0, knight_slot],
                runtime.state.y_units[0, knight_slot],
            )
        ),
        position_before_impact,
    )
    torch.testing.assert_close(runtime.state.hp[0, knight_slot], hp_before - 50.0)
    assert int(runtime.entity_status_kind[0, knight_slot]) == FAST_STATUS_STUN
    assert int(runtime.entity_status_ticks[0, knight_slot]) == 3
    position_after_impact = runtime.state.y_units[0, knight_slot].clone()

    # Effects resolve after combat, so the new stun becomes mechanics-bearing
    # on the following tick rather than retroactively suppressing this one.
    runtime.step_tick(noop)
    assert torch.equal(runtime.state.y_units[0, knight_slot], position_after_impact)
    assert int(runtime.entity_status_ticks[0, knight_slot]) == 2


def test_real_runtime_is_mask_v2_adapter_compatible() -> None:
    runtime, _ = _runtime("cpu")
    adapter = SimpleGymAdapter(runtime, no_op_action=NO_OP_ACTION)
    before = adapter.observe()
    actions = _knight_actions(runtime.device)

    step = adapter.step(
        actions,
        public_action_masks=before.legal_mask,
        public_action_mask_contract_version=PUBLIC_ACTION_MASK_CONTRACT_V2,
    )

    assert step.transition.public_action_mask_contract_version == 2
    assert step.transition.public_action_masks is before.legal_mask
    assert step.action_success.tolist() == [[True, True]]
    assert step.admission.fallback_rows == ()
    assert step.admission.all_rows_admitted
    assert step.admission.native_ticks.tolist() == [1]
    assert step.admission.committed.tolist() == [True]


def test_runtime_tick_has_no_oracle_or_resident_engine_dependency() -> None:
    source = inspect.getsource(SimpleGymRuntime.step_tick)
    for forbidden in ("BattleState", "TensorResident", ".item(", ".tolist("):
        assert forbidden not in source
