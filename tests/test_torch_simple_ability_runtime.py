from __future__ import annotations

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.rl.common import BOARD_WIDTH
from clasher.torch_sim.actions import ABILITY_ACTION, NO_OP_ACTION
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from clasher.torch_sim.simple_standard import compile_standard_simple_setup


def _runtime(device_name: str) -> tuple[SimpleGymRuntime, dict[str, int]]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        ("ArcherQueen", "Knight"),
        device=device_name,
        canonical_lane_globals=True,
    )
    fast = setup.spawn_blueprints.fast_cards
    entity = torch.zeros((2, fast.size), dtype=torch.int64, device=setup.device)
    hand = torch.zeros(fast.size, dtype=torch.int64, device=setup.device)
    for card_id in range(1, fast.size):
        kind = int(fast.kind[card_id])
        if kind >= 0:
            entity[kind, card_id] = 1_000 + card_id
        if bool(setup.public_root_mask[card_id]):
            hand[card_id] = 2_000 + card_id
    left = ["ArcherQueen", "Knight"] * 4
    right = ["Knight"] * 8
    runtime = setup.create_runtime(
        [[left, right]],
        entity_token_lookup=entity,
        hand_token_lookup=hand,
        canonical_lane_globals=True,
        starting_elixir=10.0,
        max_entities=20,
        max_effects=32,
    )
    return runtime, setup.cards.name_to_id


def _noop(runtime: SimpleGymRuntime) -> torch.Tensor:
    return torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_archer_queen_runtime_ability_is_atomic_visible_and_replayable(
    device_name: str,
) -> None:
    first, ids = _runtime(device_name)
    replay, replay_ids = _runtime(device_name)
    tile = 14 * BOARD_WIDTH + 9
    deploy = torch.tensor(
        [[tile, NO_OP_ACTION]], dtype=torch.int64, device=first.device
    )
    first_deploy = first.step_tick(deploy)
    replay_deploy = replay.step_tick(deploy.clone())
    assert first_deploy.action_success.tolist() == [[True, True]]
    assert replay_deploy.action_success.tolist() == [[True, True]]
    queen = ids["ArcherQueen"]
    assert queen == replay_ids["ArcherQueen"]
    queen_mask = first.state.active & (first.state.card_id == queen)
    queen_slot = int(queen_mask.to(torch.int64).argmax(dim=1)[0])
    replay_slot = int(
        (replay.state.active & (replay.state.card_id == queen))
        .to(torch.int64)
        .argmax(dim=1)[0]
    )
    first.state.deploy_ticks[0, queen_slot] = 0
    replay.state.deploy_ticks[0, replay_slot] = 0

    before_hand = first.action_state.hand_ids.clone()
    before_cycle = first.action_state.cycle_ids.clone()
    before_head = first.action_state.cycle_head.clone()
    before_elixir = first.action_state.elixir.clone()
    assert first.observe().legal_mask[0, 0, ABILITY_ACTION]
    ability = torch.tensor(
        [[ABILITY_ACTION, NO_OP_ACTION]], dtype=torch.int64, device=first.device
    )
    activated = first.step_tick(ability)
    replay_activated = replay.step_tick(ability.clone())
    assert activated.action_success.tolist() == [[True, True]]
    assert activated.ability_activation is not None
    assert activated.ability_activation.activated.tolist() == [[True, False]]
    assert activated.abilities is not None
    assert activated.abilities.pending[0, queen_slot]
    assert activated.abilities.cast_locked[0, queen_slot]
    assert torch.equal(first.action_state.hand_ids, before_hand)
    assert torch.equal(first.action_state.cycle_ids, before_cycle)
    assert torch.equal(first.action_state.cycle_head, before_head)
    elixir_delta = first.action_state.elixir - before_elixir
    assert -1.0 < float(elixir_delta[0, 0]) < -0.9
    assert float(elixir_delta[0, 1]) == 0.0
    assert torch.equal(activated.action_success, replay_activated.action_success)

    active_step = activated
    for _ in range(4):
        active_step = first.step_tick(_noop(first))
        replay_step = replay.step_tick(_noop(replay))
        assert torch.equal(active_step.action_success, replay_step.action_success)
        if active_step.abilities is not None and bool(
            active_step.abilities.effect_active[0, queen_slot]
        ):
            break
    assert active_step.abilities is not None
    assert active_step.abilities.effect_active[0, queen_slot]
    assert float(
        active_step.abilities.attack_speed_multiplier[0, queen_slot]
    ) == pytest.approx(2.8)
    assert float(
        active_step.abilities.movement_speed_multiplier[0, queen_slot]
    ) == pytest.approx(0.75)
    assert first.combat._target_unavailable[0, queen_slot]
    assert active_step.observation.actor.entity_features[
        0, :, queen_slot, 18
    ].tolist() == [1.0, 1.0]
    assert not active_step.observation.legal_mask[0, 0, ABILITY_ACTION]

    first.state.hp[0, queen_slot] = 0.0
    dead = first.step_tick(_noop(first))
    assert dead.abilities is not None
    assert int(dead.abilities.player.owner_stable_id[0, 0]) == 0
    assert not dead.observation.legal_mask[0, 0, ABILITY_ACTION]
    first.reset_rows(torch.ones(1, dtype=torch.bool, device=first.device))
    assert not bool(first.abilities.bound_stable_id.any())
    assert not bool(first.abilities.newest_owner_stable_id.any())


def test_standard_setup_compiles_exact_archer_queen_ability_profile() -> None:
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        ("ArcherQueen", "Knight"),
        device="cpu",
        canonical_lane_globals=True,
    )
    queen = setup.cards.name_to_id["ArcherQueen"]
    ability = setup.ability_catalog
    assert bool(ability.supported[queen])
    assert int(ability.elixir_cost[queen]) == 1
    assert (
        int(ability.trigger_delay_ticks[queen]),
        int(ability.cast_time_ticks[queen]),
        int(ability.duration_ticks[queen]),
        int(ability.cooldown_ticks[queen]),
    ) == (4, 19, 70, 340)
    assert bool(setup.supported_public_root_mask[queen])
