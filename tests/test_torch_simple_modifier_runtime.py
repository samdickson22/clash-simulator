from __future__ import annotations

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_WIDTH
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_effects import FAST_STATUS_STUN
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime


def _runtime(device_name: str) -> tuple[SimpleGymRuntime, dict[str, int]]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    loader = BattleState().card_loader
    full = TensorCardCatalog.compile(
        loader, ["Guards", "Knight", "Prince"], device=device
    )
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=loader)
    guards = full.name_to_id["Guards"]
    decks = torch.full((1, 2, 8), guards, dtype=torch.int64, device=device)
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
    lookup = torch.arange(2 * catalog.size, dtype=torch.int64, device=device).view(
        2, catalog.size
    )
    runtime = SimpleGymRuntime(
        decks,
        catalog,
        tower_spec,
        FastMatchRules(regulation_ticks=500, tiebreak_ticks=1_000),
        entity_token_lookup=lookup,
        hand_token_lookup=torch.arange(catalog.size, device=device),
        max_entities=12,
        starting_elixir=10.0,
    )
    return runtime, full.name_to_id


def _seed_knight(
    runtime: SimpleGymRuntime, ids: dict[str, int], guard_slot: int
) -> int:
    slot = 9
    knight = ids["Knight"]
    catalog = runtime.action_kernel.catalog
    state = runtime.state
    state.active[0, slot] = True
    state.stable_id[0, slot] = state.next_stable_id[0]
    state.next_stable_id.add_(1)
    state.kind[0, slot] = catalog.kind[knight]
    state.owner[0, slot] = 1
    state.card_id[0, slot] = knight
    state.x_units[0, slot] = state.x_units[0, guard_slot]
    state.y_units[0, slot] = state.y_units[0, guard_slot]
    state.hp[0, slot] = catalog.hitpoints[knight]
    state.max_hp[0, slot] = catalog.hitpoints[knight]
    state.damage[0, slot] = catalog.damage[knight]
    state.range_units[0, slot] = catalog.range_units[knight]
    state.sight_range_units[0, slot] = catalog.sight_range_units[knight]
    state.speed_units_per_tick[0, slot] = catalog.speed_units_per_tick[knight]
    state.hit_cooldown_ticks[0, slot] = catalog.hit_cooldown_ticks[knight]
    runtime._initialize_modifiers_(
        torch.nn.functional.one_hot(
            torch.tensor([slot], device=runtime.device),
            num_classes=state.max_entities,
        ).to(torch.bool)
    )
    return slot


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_guards_multisummon_shields_and_knight_whole_hits(device_name: str) -> None:
    runtime, ids = _runtime(device_name)
    deploy = torch.tensor(
        [[14 * BOARD_WIDTH + 8, NO_OP_ACTION]],
        dtype=torch.int64,
        device=runtime.device,
    )
    deployed = runtime.step_tick(deploy)
    guards = runtime.combat.spawned_mask.clone()
    assert deployed.action_success.tolist() == [[True, True]]
    assert int(guards.sum()) == 3
    assert runtime.modifiers.shield[guards].tolist() == [100.0] * 3
    assert runtime.modifiers.max_shield[guards].tolist() == [100.0] * 3

    guard_slot = int(guards[0].to(torch.int64).argmax())
    knight_slot = _seed_knight(runtime, ids, guard_slot)
    runtime.state.deploy_ticks[0, guard_slot] = 0
    runtime.entity_status_ticks[0, 6:9] = 100
    runtime.entity_status_kind[0, 6:9] = FAST_STATUS_STUN
    guard_hp = float(runtime.state.hp[0, guard_slot])
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)

    first = runtime.step_tick(noop)
    assert bool(first.effect_allocation.accepted[0, 2 + knight_slot])
    assert float(runtime.modifiers.shield[0, guard_slot]) == 0.0
    assert float(runtime.state.hp[0, guard_slot]) == guard_hp

    runtime.state.cooldown_ticks[0, knight_slot] = 0
    second = runtime.step_tick(noop)
    assert bool(second.effect_allocation.accepted[0, 2 + knight_slot])
    assert not bool(runtime.state.active[0, guard_slot])
    assert float(runtime.state.hp[0, guard_slot]) == 0.0
    assert float(runtime.modifiers.max_shield[0, guard_slot]) == 0.0


def _seed_prince_trace(
    runtime: SimpleGymRuntime, ids: dict[str, int]
) -> tuple[int, int]:
    state = runtime.state
    catalog = runtime.action_kernel.catalog
    prince_slot, target_slot = 6, 7
    prince = ids["Prince"]
    state.active[0, prince_slot : target_slot + 1] = True
    state.stable_id[0, prince_slot : target_slot + 1] = torch.tensor(
        [7, 8], device=runtime.device
    )
    state.next_stable_id[0] = 9
    state.owner[0, prince_slot : target_slot + 1] = torch.tensor(
        [0, 1], device=runtime.device
    )
    state.card_id[0, prince_slot] = prince
    state.kind[0, prince_slot : target_slot + 1] = 0
    state.x_units[0, prince_slot : target_slot + 1] = 9_000
    state.y_units[0, prince_slot : target_slot + 1] = torch.tensor(
        [10_000, 15_000], device=runtime.device
    )
    state.hp[0, prince_slot] = catalog.hitpoints[prince]
    state.max_hp[0, prince_slot] = catalog.hitpoints[prince]
    state.hp[0, target_slot] = 5_000.0
    state.max_hp[0, target_slot] = 5_000.0
    state.damage[0, prince_slot] = catalog.damage[prince]
    state.range_units[0, prince_slot] = catalog.range_units[prince]
    state.sight_range_units[0, prince_slot] = catalog.sight_range_units[prince]
    state.speed_units_per_tick[0, prince_slot] = catalog.speed_units_per_tick[prince]
    state.hit_cooldown_ticks[0, prince_slot] = catalog.hit_cooldown_ticks[prince]
    runtime.entity_status_ticks[0, target_slot] = 1_000
    runtime.entity_status_kind[0, target_slot] = FAST_STATUS_STUN
    mask = torch.zeros_like(state.active)
    mask[0, prince_slot : target_slot + 1] = True
    runtime._initialize_modifiers_(mask)
    return prince_slot, target_slot


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_prince_charge_threshold_speed_damage_and_reset(device_name: str) -> None:
    runtime, ids = _runtime(device_name)
    prince_slot, target_slot = _seed_prince_trace(runtime, ids)
    catalog = runtime.action_kernel.catalog
    prince = ids["Prince"]
    assert int(catalog.charge_threshold_distance_units[prince]) == 2_500
    assert float(catalog.charge_ready_speed_multiplier[prince]) == 2.0
    assert float(catalog.effect_damage[prince]) == 391.0

    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)
    for _ in range(42):
        runtime.step_tick(noop)
    assert bool(runtime.modifiers.charge_ready[0, prince_slot])
    assert (
        int(runtime.modifiers.charge_progress_distance_units[0, prince_slot]) == 2_520
    )

    before_y = int(runtime.state.y_units[0, prince_slot])
    runtime.step_tick(noop)
    assert int(runtime.state.y_units[0, prince_slot]) - before_y == 120

    before_hp = float(runtime.state.hp[0, target_slot])
    accepted = False
    effect_damage = 0.0
    for _ in range(20):
        result = runtime.step_tick(noop)
        command = 2 + prince_slot
        if bool(result.effect_allocation.accepted[0, command]):
            effect_slot = int(result.effect_allocation.effect_slot[0, command])
            effect_damage = float(runtime.effects.damage[0, effect_slot])
            accepted = True
            break
    assert accepted
    assert effect_damage == pytest.approx(783.0)
    assert before_hp - float(runtime.state.hp[0, target_slot]) == pytest.approx(783.0)
    assert not bool(runtime.modifiers.charge_ready[0, prince_slot])
    assert int(runtime.modifiers.charge_progress_ticks[0, prince_slot]) == 0
    assert int(runtime.modifiers.charge_progress_distance_units[0, prince_slot]) == 0
