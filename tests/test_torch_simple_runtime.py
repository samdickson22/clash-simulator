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
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime


def _runtime(
    device_name: str, *, max_entities: int = 12
) -> tuple[SimpleGymRuntime, int]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    full = TensorCardCatalog.compile(
        BattleState().card_loader, ["Knight"], device=device
    )
    catalog = FastCardCatalog.from_tensor_catalog(full)
    knight = full.name_to_id["Knight"]
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
    entity_lookup[0, knight] = 101
    entity_lookup[1, knight] = 201
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
        knight,
    )


def _knight_actions(device: torch.device) -> torch.Tensor:
    tile = 14 * BOARD_WIDTH + 8
    return torch.tensor([[tile, tile]], dtype=torch.int64, device=device)


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
    initial_gap = int(first.state.y_units[0, 7] - first.state.y_units[0, 6])

    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=first.device)
    for _ in range(80):
        first_result = first.step_tick(noop)
        replay_result = replay.step_tick(noop)

    assert int(first.state.y_units[0, 7] - first.state.y_units[0, 6]) < initial_gap
    assert bool((first.state.hp[0, 6:8] < first.state.max_hp[0, 6:8]).any())
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
