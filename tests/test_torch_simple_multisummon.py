from __future__ import annotations

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_WIDTH, NUM_TILES
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime

CARD_NAMES = ("Archers", "SkeletonArmy")


def _runtime(
    device_name: str,
    *,
    max_entities: int,
) -> tuple[SimpleGymRuntime, dict[str, int]]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    full = TensorCardCatalog.compile(
        BattleState().card_loader,
        CARD_NAMES,
        device=device,
    )
    catalog = FastCardCatalog.from_tensor_catalog(full)
    ids = {name: full.name_to_id[name] for name in CARD_NAMES}
    decks = torch.empty((1, 2, 8), dtype=torch.int64, device=device)
    decks[:, 0] = ids["Archers"]
    decks[:, 1] = ids["SkeletonArmy"]
    tower_spec = FastTowerSpec(
        card_id=torch.full((2, 3), ids["Archers"], dtype=torch.int64, device=device),
        x_units=torch.tensor(
            [[3_500, 14_500, 9_000], [3_500, 14_500, 9_000]],
            device=device,
        ),
        y_units=torch.tensor(
            [[6_500, 6_500, 2_500], [25_500, 25_500, 29_500]],
            device=device,
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
    entity_lookup[0, ids["Archers"]] = 101
    entity_lookup[0, ids["SkeletonArmy"]] = 102
    hand_lookup = torch.arange(catalog.size, dtype=torch.int64, device=device) + 100
    runtime = SimpleGymRuntime(
        decks,
        catalog,
        tower_spec,
        FastMatchRules(regulation_ticks=200, tiebreak_ticks=400),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        max_entities=max_entities,
        starting_elixir=10.0,
    )
    return runtime, ids


def _actions(device: torch.device) -> torch.Tensor:
    tile = 14 * BOARD_WIDTH + 8
    return torch.tensor([[tile, tile]], dtype=torch.int64, device=device)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_archers_and_skeleton_army_deploy_atomically_into_projection(
    device_name: str,
) -> None:
    runtime, ids = _runtime(device_name, max_entities=23)
    catalog = runtime.action_kernel.catalog
    assert int(catalog.summon_count[ids["Archers"]]) == 2
    assert int(catalog.summon_count[ids["SkeletonArmy"]]) == 15
    assert int(catalog.summon_radius_units[ids["Archers"]]) == 500
    assert int(catalog.summon_radius_units[ids["SkeletonArmy"]]) == 500

    result = runtime.step_tick(_actions(runtime.device))

    assert result.action_success.tolist() == [[True, True]]
    assert runtime.state.active.sum().item() == 23
    assert runtime.combat.spawned_mask.sum().item() == 17
    assert runtime.state.owner[0, 6:23].tolist() == [0, 0] + [1] * 15
    assert runtime.state.card_id[0, 6:8].tolist() == [ids["Archers"]] * 2
    assert runtime.state.card_id[0, 8:23].tolist() == [ids["SkeletonArmy"]] * 15
    assert runtime.state.stable_id[0, 6:23].tolist() == list(range(7, 24))
    assert runtime.state.next_stable_id.tolist() == [24]
    # World +y points from player zero's King toward player one's King. The
    # initial numeric ring is then resolved by the same dense body-contact pass
    # as every other pending entity, so a crowded 15-body swarm may push its
    # first child back toward the placement anchor on the allocation tick.
    assert runtime.state.x_units[0, 6].item() == 8_500
    assert runtime.state.y_units[0, 6].item() == 15_000
    assert runtime.state.x_units[0, 8].item() == 9_500
    assert 17_000 <= runtime.state.y_units[0, 8].item() <= 17_500
    assert torch.unique(runtime.state.x_units[0, 8:23]).numel() > 2
    assert torch.unique(runtime.state.y_units[0, 8:23]).numel() > 2
    assert result.observation.actor.entity_mask[0, 0].sum().item() == 23
    assert result.observation.actor.entity_mask[0, 1].sum().item() == 23
    assert (result.observation.actor.entity_ids[0, 0, 8:23] == 102).all()


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_joint_capacity_is_player_ordered_and_rolls_back_whole_swarm(
    device_name: str,
) -> None:
    # Sixteen ordinary slots fit Archers first, then leave only fourteen for
    # Skeleton Army. Player one must receive no partial children and no cycle
    # or elixir mutation.
    runtime, ids = _runtime(device_name, max_entities=22)
    before_hand = runtime.action_state.hand_ids.clone()
    before_cycle = runtime.action_state.cycle_ids.clone()
    before_head = runtime.action_state.cycle_head.clone()
    before_elixir = runtime.action_state.elixir.clone()

    result = runtime.step_tick(_actions(runtime.device))

    assert result.action_success.tolist() == [[True, False]]
    assert runtime.combat.spawned_mask.sum().item() == 2
    assert runtime.state.active.sum().item() == 8
    assert runtime.state.card_id[0, 6:8].tolist() == [ids["Archers"]] * 2
    assert not (runtime.state.card_id[0, 8:] == ids["SkeletonArmy"]).any()
    assert runtime.state.stable_id[0, 6:8].tolist() == [7, 8]
    assert runtime.state.next_stable_id.tolist() == [9]
    assert torch.equal(runtime.action_state.hand_ids[0, 1], before_hand[0, 1])
    assert torch.equal(runtime.action_state.cycle_ids[0, 1], before_cycle[0, 1])
    assert torch.equal(runtime.action_state.cycle_head[0, 1], before_head[0, 1])
    torch.testing.assert_close(runtime.action_state.elixir[0, 1], before_elixir[0, 1])


def test_multisummon_capacity_fails_placement_mask_closed() -> None:
    # Fourteen free slots are insufficient for the fifteen-child card while
    # the two-child card remains legal. No-op stays available for both actors.
    runtime, _ = _runtime("cpu", max_entities=20)
    mask = runtime.observe().legal_mask
    assert mask[0, 0, :NUM_TILES].any()
    assert not mask[0, 1, :NO_OP_ACTION].any()
    assert mask[0, :, NO_OP_ACTION].all()
