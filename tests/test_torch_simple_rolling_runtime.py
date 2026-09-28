from __future__ import annotations

import inspect
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
from clasher.torch_sim.simple_state import FAST_KIND_TROOP


def _runtime(
    root_name: str,
    *,
    device_name: str,
    max_entities: int = 16,
    max_rolling_spells: int = 4,
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
        hitpoints=torch.full((2, 3), 20_000.0, device=device),
        damage=torch.zeros((2, 3), device=device),
        range_units=torch.full((2, 3), 7_500, device=device),
        sight_range_units=torch.full((2, 3), 9_500, device=device),
        hit_cooldown_ticks=torch.full(
            (2, 3), 16, dtype=torch.int32, device=device
        ),
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
        kind = int(blueprints.fast_cards.kind[card_id])
        if kind >= 0:
            entity_lookup[kind, card_id] = 1_000 + card_id
        if visible_name in public_names:
            hand_lookup[card_id] = 2_000 + card_id
    return (
        SimpleGymRuntime(
            decks,
            blueprints.fast_cards,
            tower_spec,
            FastMatchRules(regulation_ticks=2_000, tiebreak_ticks=3_000),
            entity_token_lookup=entity_lookup,
            hand_token_lookup=hand_lookup,
            max_entities=max_entities,
            max_rolling_spells=max_rolling_spells,
            starting_elixir=10.0,
            spawn_blueprints=blueprints,
        ),
        blueprints,
        root,
    )


def _cast(runtime: SimpleGymRuntime, *, tile_x: int = 8, tile_y: int = 20) -> torch.Tensor:
    return torch.tensor(
        [[tile_y * BOARD_WIDTH + tile_x, NO_OP_ACTION]],
        dtype=torch.int64,
        device=runtime.device,
    )


def _noop(runtime: SimpleGymRuntime) -> torch.Tensor:
    return torch.full(
        (1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device
    )


def test_serialized_log_and_barrel_compile_as_complete_rolling_roots() -> None:
    loader = BattleState().card_loader
    base = TensorCardCatalog.compile(loader, ["Log", "BarbarianBarrel"], device="cpu")
    blueprints = FastSpawnBlueprintCatalog.compile(loader, base)
    cards = blueprints.fast_cards
    log = blueprints.cards.name_to_id["Log"]
    barrel = blueprints.cards.name_to_id["BarbarianBarrel"]

    assert cards.rolling_enabled[[log, barrel]].tolist() == [True, True]
    assert cards.training_supported[[log, barrel]].tolist() == [True, True]
    assert cards.rolling_travel_range_units[[log, barrel]].tolist() == [10_100, 4_500]
    assert cards.rolling_speed_units_per_tick[[log, barrel]].tolist() == [200, 200]
    assert cards.rolling_half_width_units[[log, barrel]].tolist() == [1_950, 1_300]
    assert cards.rolling_forward_push_units[[log, barrel]].tolist() == [700, 0]
    assert cards.rolling_ground_only[[log, barrel]].tolist() == [True, True]
    assert float(cards.rolling_tower_damage_multiplier[log]) == pytest.approx(0.13)
    row = int(blueprints.rolling_blueprint_by_card[barrel])
    assert row >= 0
    assert blueprints.visible_names[int(blueprints.child_card_id[row])] == "Barbarian"
    assert int(blueprints.rolling_blueprint_by_card[log]) == -1


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_log_full_runtime_hits_ground_once_uses_shield_and_moves_target(
    device_name: str,
) -> None:
    runtime, _, _ = _runtime("Log", device_name=device_name)
    slot = 6
    runtime.state.active[0, slot] = True
    runtime.state.stable_id[0, slot] = 7
    runtime.state.kind[0, slot] = FAST_KIND_TROOP
    runtime.state.owner[0, slot] = 1
    runtime.state.x_units[0, slot] = 9_000
    runtime.state.y_units[0, slot] = 2_700
    runtime.state.hp[0, slot] = 1_000.0
    runtime.state.max_hp[0, slot] = 1_000.0
    runtime.modifiers.shield[0, slot] = 100.0
    runtime.modifiers.max_shield[0, slot] = 100.0

    result = runtime.step_tick(_cast(runtime))
    assert result.action_success.tolist() == [[True, True]]
    assert result.rolling_allocation.accepted.tolist() == [[True, False]]
    assert int(runtime.rolling_spells.origin_x_units[0, 0]) == 9_000
    assert int(runtime.rolling_spells.origin_y_units[0, 0]) == 2_500
    assert bool(result.rolling.hit[0, 0, slot])
    assert float(runtime.modifiers.shield[0, slot]) == 0.0
    assert float(runtime.state.hp[0, slot]) == 1_000.0
    assert int(runtime.state.y_units[0, slot]) > 2_700

    second = runtime.step_tick(_noop(runtime))
    assert not bool(second.rolling.hit[0, 0, slot])
    assert float(runtime.state.hp[0, slot]) == 1_000.0


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_log_full_runtime_scales_tower_damage_without_displacing_it(
    device_name: str,
) -> None:
    runtime, blueprints, root = _runtime("Log", device_name=device_name)
    tower = 3
    runtime.state.x_units[0, tower] = 9_000
    runtime.state.y_units[0, tower] = 2_700
    runtime.state.hp[0, tower] = 1_000.0
    runtime.state.max_hp[0, tower] = 1_000.0
    before = runtime.state.x_units[0, tower].clone(), runtime.state.y_units[0, tower].clone()
    result = runtime.step_tick(_cast(runtime))
    expected = float(blueprints.fast_cards.rolling_damage[root]) * 0.13
    assert float(runtime.state.hp[0, tower]) == pytest.approx(1_000.0 - expected)
    assert int(runtime.state.x_units[0, tower]) == int(before[0])
    assert int(runtime.state.y_units[0, tower]) == int(before[1])
    assert bool(result.rolling.hit[0, 0, tower])


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_barbarian_barrel_rolls_then_spawns_typed_child_deterministically(
    device_name: str,
) -> None:
    first, blueprints, root = _runtime("BarbarianBarrel", device_name=device_name)
    replay, replay_blueprints, replay_root = _runtime(
        "BarbarianBarrel", device_name=device_name
    )
    assert root == replay_root
    action = _cast(first)
    left = first.step_tick(action)
    replay.step_tick(action.clone())
    assert left.action_success.tolist() == [[True, True]]
    for _ in range(30):
        if left.rolling_spawn_allocation is not None and bool(
            left.rolling_spawn_allocation.accepted.any()
        ):
            break
        left = first.step_tick(_noop(first))
        replay.step_tick(_noop(replay))
    else:
        raise AssertionError("Barbarian Barrel did not terminate within range")

    assert left.rolling_spawn_allocation is not None
    assert int(left.rolling_spawn_allocation.spawned_mask.sum()) == 1
    barbarian = next(
        card_id
        for card_id, name in enumerate(blueprints.visible_names)
        if name == "Barbarian"
    )
    child = first.state.active & (first.state.card_id == barbarian)
    assert int(child.sum()) == 1
    assert first.state.deploy_ticks[child].tolist() == [20]
    assert int(first.projector.inputs.hand_token_lookup[barbarian]) == 0
    token = int(first.projector.inputs.entity_token_lookup[0, barbarian])
    visible = left.observation.actor.entity_ids[0, 0][
        left.observation.actor.entity_mask[0, 0]
    ]
    assert bool((visible == token).any())
    assert blueprints.cards.names == replay_blueprints.cards.names
    for descriptor in fields(first.state):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(first.state, descriptor.name),
                getattr(replay.state, descriptor.name),
            )
    for descriptor in fields(first.rolling_spells):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(first.rolling_spells, descriptor.name),
                getattr(replay.rolling_spells, descriptor.name),
            )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_rolling_pool_capacity_masks_and_rolls_back_second_cast(
    device_name: str,
) -> None:
    runtime, _, _ = _runtime(
        "Log", device_name=device_name, max_rolling_spells=1
    )
    first = runtime.step_tick(_cast(runtime))
    assert first.action_success.tolist() == [[True, True]]
    observation = runtime.observe()
    assert not bool(observation.legal_mask[0, 0, :NUM_TILES].any())
    before_hand = runtime.action_state.hand_ids.clone()
    before_elixir = runtime.action_state.elixir.clone()
    rejected = runtime.step_tick(_cast(runtime))
    assert rejected.action_success.tolist() == [[False, True]]
    assert torch.equal(runtime.action_state.hand_ids, before_hand)
    assert bool((runtime.action_state.elixir >= before_elixir).all())


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_barrel_terminal_spawn_capacity_is_masked_before_spend(
    device_name: str,
) -> None:
    runtime, _, _ = _runtime(
        "BarbarianBarrel", device_name=device_name, max_entities=7
    )
    runtime.state.active[0, 6] = True
    runtime.state.stable_id[0, 6] = 7
    runtime.state.kind[0, 6] = FAST_KIND_TROOP
    runtime.state.owner[0, 6] = 1
    runtime.state.hp[0, 6] = 1_000.0
    runtime.state.max_hp[0, 6] = 1_000.0
    assert not bool(runtime.observe().legal_mask[0, 0, :NUM_TILES].any())
    before_hand = runtime.action_state.hand_ids.clone()
    before_elixir = runtime.action_state.elixir.clone()
    result = runtime.step_tick(_cast(runtime))
    assert result.action_success.tolist() == [[False, True]]
    assert torch.equal(runtime.action_state.hand_ids, before_hand)
    assert bool((runtime.action_state.elixir >= before_elixir).all())
    assert not bool(runtime.rolling_spells.active.any())


def test_spawn_free_log_does_not_reserve_an_entity_slot() -> None:
    runtime, _, _ = _runtime("Log", device_name="cpu", max_entities=7)
    runtime.state.active[0, 6] = True
    runtime.state.stable_id[0, 6] = 7
    runtime.state.kind[0, 6] = FAST_KIND_TROOP
    runtime.state.owner[0, 6] = 1
    runtime.state.hp[0, 6] = 1_000.0
    runtime.state.max_hp[0, 6] = 1_000.0
    assert bool(runtime.observe().legal_mask[0, 0, :NUM_TILES].all())
    assert runtime.step_tick(_cast(runtime)).action_success.tolist() == [[True, True]]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_selective_reset_clears_owned_rolling_pool(device_name: str) -> None:
    runtime, _, _ = _runtime("Log", device_name=device_name)
    runtime.step_tick(_cast(runtime))
    assert bool(runtime.rolling_spells.active.any())
    runtime.reset_rows(
        torch.ones((1,), dtype=torch.bool, device=runtime.device)
    )
    assert not bool(runtime.rolling_spells.active.any())
    assert not bool(runtime.rolling_spells.hit_stable_ids.any())
    assert bool(runtime.observe().legal_mask[0, 0, :NUM_TILES].all())


def test_runtime_rolling_seam_has_no_card_name_or_host_sync_dispatch() -> None:
    source = inspect.getsource(SimpleGymRuntime._rolling_commands) + inspect.getsource(
        SimpleGymRuntime.step_tick
    )
    for forbidden in ("Log", "BarbarianBarrel", ".item(", ".tolist(", ".cpu("):
        assert forbidden not in source
