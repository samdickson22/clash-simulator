from __future__ import annotations

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_WIDTH
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_effects import FAST_EFFECT_AREA
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime


def _runtime(
    names: list[str],
    deck_name: str,
    *,
    device_name: str,
    max_entities: int,
) -> tuple[SimpleGymRuntime, TensorCardCatalog, FastCardCatalog]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    loader = BattleState().card_loader
    full = TensorCardCatalog.compile(loader, names, device=device)
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=loader)
    deck_id = full.name_to_id[deck_name]
    decks = torch.full((1, 2, 8), deck_id, dtype=torch.int64, device=device)
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
        hit_cooldown_ticks=torch.full(
            (2, 3), 16, dtype=torch.int32, device=device
        ),
    )
    entity_lookup = torch.arange(
        2 * catalog.size, dtype=torch.int64, device=device
    ).view(2, catalog.size)
    hand_lookup = torch.arange(catalog.size, dtype=torch.int64, device=device)
    runtime = SimpleGymRuntime(
        decks,
        catalog,
        tower_spec,
        FastMatchRules(regulation_ticks=2_000, tiebreak_ticks=3_000),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        max_entities=max_entities,
    )
    return runtime, full, catalog


def _deploy_player_zero(runtime: SimpleGymRuntime) -> torch.Tensor:
    tile = 14 * BOARD_WIDTH + 8
    return torch.tensor(
        [[tile, NO_OP_ACTION]], dtype=torch.int64, device=runtime.device
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_runtime_cannon_expires_on_catalog_lifetime_and_reopens_capacity(
    device_name: str,
) -> None:
    runtime, full, catalog = _runtime(
        ["Cannon"], "Cannon", device_name=device_name, max_entities=7
    )
    cannon = full.name_to_id["Cannon"]
    assert int(catalog.lifetime_ticks[cannon]) == 600

    deployed = runtime.step_tick(_deploy_player_zero(runtime))
    assert deployed.action_success.tolist() == [[True, True]]
    assert int(runtime.lifecycle.lifetime_ticks[0, 6]) == 599
    assert not runtime.observe().legal_mask[:, :, :NO_OP_ACTION].any()

    noop = torch.full(
        (1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device
    )
    for _ in range(598):
        runtime.step_tick(noop)
    assert bool(runtime.state.active[0, 6])
    assert int(runtime.lifecycle.lifetime_ticks[0, 6]) == 1

    expired = runtime.step_tick(noop)
    assert not bool(runtime.state.active[0, 6])
    assert int(runtime.state.stable_id[0, 6]) == 0
    assert expired.observation.legal_mask[:, :, :NO_OP_ACTION].any()


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_runtime_resolvable_death_spawn_uses_child_catalog_and_clears_status(
    device_name: str,
) -> None:
    runtime, full, catalog = _runtime(
        ["Skeleton", "Tombstone"],
        "Tombstone",
        device_name=device_name,
        max_entities=11,
    )
    skeleton = full.name_to_id["Skeleton"]
    tombstone = full.name_to_id["Tombstone"]
    assert int(catalog.death_spawn_card_id[tombstone]) == skeleton
    assert int(catalog.death_spawn_count[tombstone]) == 4

    runtime.step_tick(_deploy_player_zero(runtime))
    parent_slot = 6
    runtime.entity_status_kind[0, parent_slot] = 1
    runtime.entity_status_ticks[0, parent_slot] = 8
    runtime.effects.active[0, 0] = True
    runtime.effects.kind[0, 0] = FAST_EFFECT_AREA
    runtime.effects.source_owner[0, 0] = 1
    runtime.effects.x_units[0, 0] = runtime.state.x_units[0, parent_slot]
    runtime.effects.y_units[0, 0] = runtime.state.y_units[0, parent_slot]
    runtime.effects.damage[0, 0] = runtime.state.hp[0, parent_slot]
    runtime.effects.radius_units[0, 0] = 1
    runtime.effects.lifetime_ticks[0, 0] = 1
    noop = torch.full(
        (1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device
    )
    result = runtime.step_tick(noop)

    assert bool(result.effects.impacted[0, 0])
    assert bool(result.effects.targets_hit[0, 0, parent_slot])
    children = runtime.state.active & (runtime.state.card_id == skeleton)
    assert int(children.sum()) == 4
    assert runtime.state.stable_id[children].tolist() == [8, 9, 10, 11]
    torch.testing.assert_close(
        runtime.state.damage[children],
        torch.full_like(
            runtime.state.damage[children], float(catalog.damage[skeleton])
        ),
    )
    assert not bool(runtime.entity_status_ticks[children].any())
    assert bool(result.observation.actor.entity_mask[:, :, 6:10].all())


def test_unresolved_internal_death_spawn_identity_fails_closed() -> None:
    loader = BattleState().card_loader
    full = TensorCardCatalog.compile(loader, ["Golem"], device="cpu")
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=loader)
    golem = full.name_to_id["Golem"]

    assert int(catalog.death_spawn_card_id[golem]) == 0
    assert int(catalog.death_spawn_count[golem]) == 0
