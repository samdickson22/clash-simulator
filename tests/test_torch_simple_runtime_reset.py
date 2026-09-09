from __future__ import annotations

from dataclasses import fields, replace
from types import SimpleNamespace

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_WIDTH
from clasher.rl.seeded_deals import SeededDealSchedule
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_adapter import SimpleGymAdapter, SimpleGymHistory
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_effects import FAST_STATUS_STUN
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_rollout import SimpleGymRolloutBridge
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from scripts.collect_hog26_complete_outcomes import install_seeded_deals


def _runtime(device_name: str) -> tuple[SimpleGymRuntime, dict[str, int]]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.empty(0, device=device_name).device
    full = TensorCardCatalog.compile(
        BattleState().card_loader, ["Knight", "Archers"], device="cpu"
    )

    catalog = FastCardCatalog.from_tensor_catalog(full)
    catalog = replace(
        catalog,
        device=device,
        **{
            field.name: getattr(catalog, field.name).to(device)
            for field in fields(catalog)
            if isinstance(getattr(catalog, field.name), torch.Tensor)
        },
    )
    ids = {name: full.name_to_id[name] for name in ("Knight", "Archers")}
    decks = torch.full((2, 2, 8), ids["Knight"], dtype=torch.int64, device=device)
    tower_spec = FastTowerSpec(
        card_id=torch.full((2, 3), ids["Knight"], dtype=torch.int64, device=device),
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
    entity_lookup[0, ids["Knight"]] = 101
    entity_lookup[0, ids["Archers"]] = 102
    entity_lookup[1, ids["Knight"]] = 201
    hand_lookup = torch.arange(catalog.size, dtype=torch.int64, device=device) + 100
    return (
        SimpleGymRuntime(
            decks,
            catalog,
            tower_spec,
            FastMatchRules(regulation_ticks=20, tiebreak_ticks=40),
            entity_token_lookup=entity_lookup,
            hand_token_lookup=hand_lookup,
            max_entities=14,
            max_effects=8,
        ),
        ids,
    )


@pytest.mark.parametrize("device_name", ["cpu", "mps"])
def test_seeded_deals_are_applied_to_public_hand_and_cycle(device_name):
    if device_name == "mps" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    runtime, ids = _runtime(device_name)
    own = torch.tensor(
        [ids["Knight"]] * 4 + [ids["Archers"]] * 4,
        dtype=torch.int64,
        device=runtime.device,
    )
    opponent = own.flip(0)
    base = torch.stack([torch.stack([own, opponent]), torch.stack([opponent, own])])
    schedule = SeededDealSchedule(
        base,
        torch.tensor([0, 1], device=runtime.device),
        ["paired", "paired"],
        seed=71,
        episodes=4,
    )
    first = schedule.initial_decks()
    observation = runtime.reset_rows(
        torch.ones(2, dtype=torch.bool, device=runtime.device), deck_ids=first
    )
    assert torch.equal(runtime.action_state.hand_ids, first[:, :, :4])
    assert torch.equal(runtime.action_state.cycle_ids, first[:, :, 4:])
    assert torch.equal(observation.actor.hand_ids, first[:, :, :5] + 100)
    mask = torch.tensor([True, False], device=runtime.device)
    next_decks = schedule(0, mask, None)
    observation = runtime.reset_rows(mask, deck_ids=next_decks)
    assert torch.equal(observation.actor.hand_ids[0], next_decks[0, :, :5] + 100)
    assert torch.equal(observation.actor.hand_ids[1], first[1, :, :5] + 100)


def _placement_actions(runtime: SimpleGymRuntime) -> torch.Tensor:
    tile = 14 * BOARD_WIDTH + 8
    return torch.full(
        (runtime.batch_size, 2), tile, dtype=torch.int64, device=runtime.device
    )


def _row_snapshot(runtime: SimpleGymRuntime, row: int) -> dict[str, torch.Tensor]:
    snapshot: dict[str, torch.Tensor] = {}
    for group_name, group in (
        ("state", runtime.state),
        ("action", runtime.action_state),
        ("effects", runtime.effects),
        ("lifecycle", runtime.lifecycle),
        ("modifiers", runtime.modifiers),
        ("navigation", runtime.combat.navigation.state),
        ("policy", runtime.policy_mechanics),
    ):
        for descriptor in fields(group):
            value = getattr(group, descriptor.name)
            if isinstance(value, torch.Tensor):
                snapshot[f"{group_name}.{descriptor.name}"] = value[row].clone()
    for name, value in (
        ("status_kind", runtime.entity_status_kind),
        ("status_ticks", runtime.entity_status_ticks),
        ("consume", runtime.effect_consume_source_id),
        ("projection_hand", runtime._projection_hand_ids),
        ("double", runtime._double_elixir),
        ("triple", runtime._triple_elixir),
        ("ability_cooldown", runtime._ability_cooldown),
        ("ability_duration", runtime._ability_duration),
        ("refill", runtime._refill_cooldown_ms),
        ("visibility", runtime.projector.inputs.public_visibility),
        ("spawned", runtime.combat.spawned_mask),
        ("target_unavailable", runtime.combat._target_unavailable),
        ("entity_special", runtime._entity_special),
        ("entity_invisible", runtime._entity_invisible),
        ("entity_hidden", runtime._entity_hidden),
        ("initial_hp", runtime.outcomes.initial_tower_hp),
        ("previous_hp", runtime.outcomes.previous_tower_hp),
        ("previous_crowns", runtime.outcomes.previous_crowns),
        ("overtime", runtime.outcomes.overtime),
    ):
        snapshot[name] = value[row].clone()
    return snapshot


def _assert_actor_row_equal(actual: object, expected: object, row: int) -> None:
    for name in (
        "entity_ids",
        "entity_features",
        "entity_mask",
        "hand_ids",
        "global_features",
    ):
        assert torch.equal(getattr(actual, name)[row], getattr(expected, name)[row])


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_selective_reset_restores_exact_episode_and_preserves_live_row(
    device_name: str,
) -> None:
    runtime, ids = _runtime(device_name)
    initial = runtime.observe()
    runtime.step_tick(_placement_actions(runtime))
    noop = torch.full(
        (runtime.batch_size, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device
    )
    for _ in range(3):
        runtime.step_tick(noop)

    # Exercise planes which are not guaranteed to be touched by a Knight tick.
    runtime.effects.active[0, 0] = True
    runtime.effects.damage[0, 0] = 123.0
    runtime.entity_status_ticks[0, 6] = 9
    runtime.entity_status_kind[0, 6] = FAST_STATUS_STUN
    runtime.modifiers.shield[0, 6] = 77.0
    runtime.lifecycle.lifetime_ticks[0, 6] = 11
    runtime.combat.navigation.state.mover_stable_id[0, 6] = 7
    runtime.combat.navigation.state.target_stable_id[0, 6] = 4
    runtime.combat.navigation.state.route_phase[0, 6] = 2
    runtime.combat.navigation.state.bridge_index[0, 6] = 0
    runtime.combat.navigation.state.travel_direction[0, 6] = 1
    runtime.effect_consume_source_id[0, 0] = 7
    runtime.projector.inputs.public_visibility[0, :, 6] = False
    runtime.state.hp[0, 2] = 0.0
    terminal = runtime.step_tick(noop)
    assert bool(terminal.done[0])
    assert not bool(terminal.done[1])
    live_before = _row_snapshot(runtime, 1)

    reset_observation = runtime.reset_rows(
        torch.tensor([True, False], dtype=torch.bool, device=runtime.device)
    )

    assert not bool(runtime.state.game_over[0])
    assert int(runtime.state.winner[0]) == -2
    assert int(runtime.state.tick[0]) == 0
    assert int(runtime.state.next_stable_id[0]) == 7
    assert runtime.state.stable_id[0, :6].tolist() == [1, 2, 3, 4, 5, 6]
    assert not runtime.state.active[0, 6:].any()
    assert not runtime.effects.active[0].any()
    assert not runtime.entity_status_ticks[0].any()
    assert not runtime.lifecycle.lifetime_ticks[0].any()
    assert not runtime.modifiers.shield[0].any()
    assert not runtime.combat.navigation.state.mover_stable_id[0].any()
    assert not runtime.combat.navigation.state.target_stable_id[0].any()
    assert not runtime.combat.navigation.state.route_phase[0].any()
    assert runtime.combat.navigation.state.bridge_index[0].eq(-1).all()
    assert not runtime.combat.navigation.state.travel_direction[0].any()
    assert not runtime.policy_mechanics.bound_stable_id[0].any()
    assert not runtime._entity_special[0].any()
    assert not runtime._entity_invisible[0].any()
    assert not runtime._entity_hidden[0].any()
    assert not runtime.outcomes.overtime[0]
    _assert_actor_row_equal(reset_observation.actor, initial.actor, 0)
    assert torch.equal(reset_observation.legal_mask[0], initial.legal_mask[0])

    live_after = _row_snapshot(runtime, 1)
    assert live_before.keys() == live_after.keys()
    for name in live_before:
        assert torch.equal(live_before[name], live_after[name]), name

    # The selected row restarts its episode-local monotonic identity sequence.
    actions = _placement_actions(runtime)
    actions[0, 1] = NO_OP_ACTION
    actions[1] = NO_OP_ACTION
    runtime.step_tick(actions)
    assert int(runtime.state.stable_id[0, 6]) == 7
    runtime.step_tick(actions)
    assert runtime.state.stable_id[0, 6:8].tolist() == [7, 8]
    assert int(runtime.state.next_stable_id[0]) == 9
    assert int(runtime.state.card_id[0, 6]) == ids["Knight"]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_reset_rows_accepts_new_decks_and_leaves_adapter_history_owned_separately(
    device_name: str,
) -> None:
    runtime, ids = _runtime(device_name)
    adapter = SimpleGymAdapter(runtime, no_op_action=NO_OP_ACTION)
    noop = torch.full(
        (runtime.batch_size, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device
    )
    adapter.step(noop)
    history_before = adapter.history
    new_decks = torch.full(
        (runtime.batch_size, 2, 8),
        ids["Archers"],
        dtype=torch.int64,
        device=runtime.device,
    )
    reset_mask = torch.tensor([True, False], dtype=torch.bool, device=runtime.device)

    observation = runtime.reset_rows(reset_mask, deck_ids=new_decks)

    assert runtime.action_state.hand_ids[0].eq(ids["Archers"]).all()
    assert runtime.action_state.cycle_ids[0].eq(ids["Archers"]).all()
    assert runtime.action_state.cycle_head[0].eq(0).all()
    assert runtime.action_state.hand_ids[1].eq(ids["Knight"]).all()
    assert observation.actor.hand_ids[0].eq(ids["Archers"] + 100).all()
    assert adapter.history is history_before
    assert not adapter.history.episode_starts.any()

    # Rollout code can reset recurrent history on its own schedule.
    initial_history = SimpleGymHistory.initial(
        runtime.batch_size, device=runtime.device, no_op_action=NO_OP_ACTION
    )
    adapter.history = SimpleGymHistory(
        previous_actions=torch.where(
            reset_mask[:, None],
            initial_history.previous_actions,
            adapter.history.previous_actions,
        ),
        previous_rewards=torch.where(
            reset_mask[:, None],
            initial_history.previous_rewards,
            adapter.history.previous_rewards,
        ),
        episode_starts=torch.where(
            reset_mask[:, None],
            initial_history.episode_starts,
            adapter.history.episode_starts,
        ),
    )
    assert adapter.history.episode_starts.tolist() == [[True, True], [False, False]]


def test_reset_rows_rejects_malformed_batch_contract() -> None:
    runtime, _ = _runtime("cpu")
    with pytest.raises(ValueError, match="shape"):
        runtime.reset_rows(torch.ones((2, 1), dtype=torch.bool))
    with pytest.raises(ValueError, match="bool"):
        runtime.reset_rows(torch.ones(2, dtype=torch.int64))
    with pytest.raises(ValueError, match="int64"):
        runtime.reset_rows(
            torch.ones(2, dtype=torch.bool),
            torch.ones((2, 2, 8), dtype=torch.int32),
        )


@pytest.mark.parametrize("device_name", ["cpu", "mps"])
def test_collection_deal_installation_resets_history_and_records_own_hand(device_name):
    if device_name == "mps" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    runtime, ids = _runtime(device_name)
    base = (
        torch.tensor([ids["Knight"]] * 4 + [ids["Archers"]] * 4, device=runtime.device)
        .expand(2, 2, 8)
        .clone()
    )
    runtime.reset_rows(
        torch.ones(2, dtype=torch.bool, device=runtime.device), deck_ids=base
    )
    bridge = SimpleGymRolloutBridge(runtime)
    bridge.adapter.history.previous_rewards.fill_(3)
    bridge.adapter.history.episode_starts.fill_(False)
    collector = SimpleNamespace(
        collector=SimpleNamespace(bridge=bridge),
        metadata=SimpleNamespace(opponent_deck_names=("toy", "toy")),
        learner_players=torch.tensor([0, 1], device=runtime.device),
    )
    metadata = install_seeded_deals(
        collector, ["balanced", "balanced"], seed=72, episodes=4
    )
    boundary = bridge.observe()
    assert boundary.episode_starts.all()
    assert not boundary.previous_rewards.any()
    for row, seat in enumerate([0, 1]):
        assert (
            boundary.actor.hand_ids[row, seat].tolist()
            == metadata["initial_actor_hand_tokens_by_stream"][row][0]
        )
    schedule = collector.collector.reset_deck_provider
    mask = torch.tensor([False, True], device=runtime.device)
    boundary = bridge.reset_done(mask, deck_ids=schedule(0, mask, None))
    assert (
        boundary.actor.hand_ids[1, 1].tolist()
        == metadata["initial_actor_hand_tokens_by_stream"][1][1]
    )
    assert (
        boundary.actor.hand_ids[0, 0].tolist()
        == metadata["initial_actor_hand_tokens_by_stream"][0][0]
    )
