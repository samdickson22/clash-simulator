from __future__ import annotations

import inspect
from dataclasses import fields, replace
from typing import Any, ClassVar, cast

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.simple_tensor_collector import (
    SIMPLE_TENSOR_ACTOR_SEMANTICS_ID,
    SIMPLE_TENSOR_BACKEND_ID,
    SimplePublicActionMaskV2,
    SimpleTensorCollector,
    SimpleTensorCollectorError,
    SimpleTensorMaskRequest,
    SimpleTensorPolicyBoundary,
    SimpleTensorPolicyDecision,
)
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_reward_v2 import (
    SIMPLE_REWARD_V2_CONTRACT_ID,
    SimpleRewardV2Config,
)
from clasher.torch_sim.simple_rollout import (
    SimpleGymRolloutBridge,
    SimpleGymRolloutStep,
)
from clasher.torch_sim.simple_runtime import SimpleGymRuntime


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _bridge(
    device_name: str,
) -> tuple[SimpleGymRolloutBridge, dict[str, int]]:
    device = _device(device_name)
    full = TensorCardCatalog.compile(
        BattleState().card_loader,
        ["Knight", "Archers"],
        device=device,
    )
    fast = FastCardCatalog.from_tensor_catalog(full)
    ids = {name: full.name_to_id[name] for name in ("Knight", "Archers")}
    decks = torch.full((2, 2, 8), ids["Knight"], dtype=torch.int64, device=device)
    towers = FastTowerSpec(
        card_id=torch.full((2, 3), ids["Knight"], dtype=torch.int64, device=device),
        x_units=torch.tensor(
            ((3_500, 14_500, 9_000), (3_500, 14_500, 9_000)),
            dtype=torch.int32,
            device=device,
        ),
        y_units=torch.tensor(
            ((6_500, 6_500, 2_500), (25_500, 25_500, 29_500)),
            dtype=torch.int32,
            device=device,
        ),
        hitpoints=torch.tensor(
            ((2_000.0, 2_000.0, 3_000.0),) * 2,
            dtype=torch.float32,
            device=device,
        ),
        damage=torch.zeros((2, 3), dtype=torch.float32, device=device),
        range_units=torch.full(
            (2, 3), 7_500, dtype=torch.int32, device=device
        ),
        sight_range_units=torch.full(
            (2, 3), 9_500, dtype=torch.int32, device=device
        ),
        hit_cooldown_ticks=torch.full(
            (2, 3), 16, dtype=torch.int32, device=device
        ),
    )
    hand_lookup = torch.arange(fast.size, dtype=torch.int64, device=device) + 100
    entity_lookup = hand_lookup.view(1, -1).expand(5, -1).clone()
    runtime = SimpleGymRuntime(
        decks,
        fast,
        towers,
        FastMatchRules(regulation_ticks=20, tiebreak_ticks=80),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        max_entities=16,
        max_effects=8,
        include_privileged_critic=True,
    )
    bridge = SimpleGymRolloutBridge(
        runtime,
        decision_interval=8,
        reward_v2_config=SimpleRewardV2Config(gamma=0.995),
    )
    return bridge, ids


class _NoopPublicMask:
    semantics: ClassVar[dict[str, object]] = {
        "schema": "test.label-independent.noop-only.v2",
        "uses_expert_labels": False,
        "simulator_legal_mask_is_separate": True,
    }

    def __init__(self, *, contract_version: int = 2) -> None:
        self.contract_version = contract_version

    def __call__(self, request: SimpleTensorMaskRequest) -> SimplePublicActionMaskV2:
        masks = torch.zeros_like(request.observation.legal_mask)
        masks[:, :, NO_OP_ACTION] = True
        return SimplePublicActionMaskV2(
            masks=masks,
            semantics_id="test-noop-public-mask-v2",
            semantics=self.semantics,
            contract_version=self.contract_version,
        )


class _RecurrentNoopPolicy:
    def __call__(
        self, boundary: SimpleTensorPolicyBoundary
    ) -> SimpleTensorPolicyDecision:
        assert not torch.equal(boundary.public_action_masks, boundary.legal_mask)
        assert boundary.recurrent_inputs is not None
        hidden = boundary.recurrent_inputs["hidden"]
        actions = torch.full(
            hidden.shape[:2],
            NO_OP_ACTION,
            dtype=torch.int64,
            device=hidden.device,
        )
        return SimpleTensorPolicyDecision(
            actions=actions,
            next_recurrent_inputs={"hidden": hidden + 1.0},
            storage={
                "log_prob": torch.full_like(hidden[..., 0], -0.25),
                "value": hidden[..., 0].clone(),
            },
        )


class _ArchersReset:
    def __init__(self, bridge: SimpleGymRolloutBridge, archer_id: int) -> None:
        self.bridge = bridge
        self.archer_id = archer_id

    def __call__(
        self,
        decision_index: int,
        reset_mask: torch.Tensor,
        step: SimpleGymRolloutStep,
    ) -> torch.Tensor:
        del decision_index, reset_mask, step
        return torch.full(
            (self.bridge.batch_size, 2, 8),
            self.archer_id,
            dtype=torch.int64,
            device=self.bridge.device,
        )


def _collector(device_name: str) -> tuple[SimpleTensorCollector, int]:
    bridge, ids = _bridge(device_name)
    bridge.runtime.state.hp[0, 2] = 0.0
    return (
        SimpleTensorCollector(
            bridge,
            public_mask_provider=_NoopPublicMask(),
            policy=_RecurrentNoopPolicy(),
            reset_deck_provider=_ArchersReset(bridge, ids["Archers"]),
        ),
        ids["Archers"],
    )


def _assert_equal(left: Any, right: Any) -> None:
    if isinstance(left, torch.Tensor):
        assert isinstance(right, torch.Tensor)
        assert torch.equal(left, right)
        return
    if isinstance(left, dict):
        assert isinstance(right, dict)
        assert tuple(left) == tuple(right)
        for key in left:
            _assert_equal(left[key], right[key])
        return
    if hasattr(left, "__dataclass_fields__"):
        assert type(left) is type(right)
        for descriptor in fields(left):
            _assert_equal(getattr(left, descriptor.name), getattr(right, descriptor.name))
        return
    assert left == right


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_deterministic_mixed_done_reset_stays_device_resident(
    device_name: str,
) -> None:
    left, archer_id = _collector(device_name)
    right, _ = _collector(device_name)
    initial = {
        "hidden": torch.zeros(
            (left.batch_size, 2, 3), dtype=torch.float32, device=left.device
        )
    }

    actual = left.collect(3, recurrent_inputs=initial)
    expected = right.collect(
        3,
        recurrent_inputs={"hidden": initial["hidden"].clone()},
    )

    _assert_equal(actual, expected)
    assert actual.actions.shape == (3, 2, 2)
    assert actual.actor.entity_ids.shape[:3] == (3, 2, 2)
    assert actual.critic is not None
    assert actual.critic.entity_ids.shape[:3] == (3, 2, 2)
    assert actual.done.tolist() == [[True, False], [False, False], [False, False]]
    assert actual.native_ticks.tolist() == [[1, 8], [8, 8], [8, 8]]
    assert torch.equal(actual.reset_masks, actual.done)
    assert actual.episode_starts[0].all()
    assert actual.episode_starts[1, 0].all()
    assert not actual.episode_starts[1, 1].any()
    assert not actual.episode_starts[2].any()
    assert actual.committed.all()
    assert actual.all_rows_admitted.all()
    assert not actual.fallback_rows.any()
    assert actual.public_action_masks[:, :, :, NO_OP_ACTION].all()
    assert not torch.equal(actual.public_action_masks, actual.legal_masks)
    assert actual.recurrent_inputs is not None
    assert actual.recurrent_inputs["hidden"][:, 0, 0, 0].tolist() == [0.0, 1.0, 2.0]
    assert actual.policy_storage["value"][:, 0, 0].tolist() == [0.0, 1.0, 2.0]
    assert actual.bootstrap.recurrent_inputs is not None
    assert actual.bootstrap.recurrent_inputs["hidden"][0, 0, 0].item() == 3.0
    expected_archer_token = archer_id + 100
    assert actual.actor.hand_ids[1, 0].eq(expected_archer_token).all()
    assert actual.actor.hand_ids[1, 1].ne(expected_archer_token).all()
    assert actual.metadata.backend_id == SIMPLE_TENSOR_BACKEND_ID
    assert actual.metadata.admission_validation == "device-async-after-rollout"
    assert actual.metadata.actor_semantics_id == SIMPLE_TENSOR_ACTOR_SEMANTICS_ID
    assert actual.metadata.public_action_mask_contract_version == 2
    assert actual.metadata.reward_contract_id == SIMPLE_REWARD_V2_CONTRACT_ID
    assert actual.metadata.decision_interval == 8
    for descriptor in fields(actual):
        value = getattr(actual, descriptor.name)
        if isinstance(value, torch.Tensor):
            assert value.device == left.device


def test_v1_public_mask_fails_before_runtime_mutation() -> None:
    bridge, _ = _bridge("cpu")
    collector = SimpleTensorCollector(
        bridge,
        public_mask_provider=_NoopPublicMask(contract_version=1),
        policy=_RecurrentNoopPolicy(),
    )
    tick_before = bridge.runtime.state.tick.clone()

    with pytest.raises(SimpleTensorCollectorError, match="contract v2"):
        collector.collect(
            1,
            recurrent_inputs={"hidden": torch.zeros((2, 2, 3))},
        )

    assert torch.equal(bridge.runtime.state.tick, tick_before)


def test_collector_rejects_noncommitted_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, _ = _collector("cpu")
    collector.strict_host_validation = True
    original = collector.bridge.step

    def noncommitted(*args: object, **kwargs: object) -> SimpleGymRolloutStep:
        step = cast(SimpleGymRolloutStep, cast(Any, original)(*args, **kwargs))
        return replace(step, committed=torch.zeros_like(step.committed))

    monkeypatch.setattr(collector.bridge, "step", noncommitted)
    with pytest.raises(SimpleTensorCollectorError, match="native-admission"):
        collector.collect(
            1,
            recurrent_inputs={"hidden": torch.zeros((2, 2, 3))},
        )


def test_collector_requires_objective_reward_contract() -> None:
    bridge, _ = _bridge("cpu")
    legacy = SimpleGymRolloutBridge(bridge.runtime, decision_interval=8)
    with pytest.raises(SimpleTensorCollectorError, match="objective-v1-gamma-v1"):
        SimpleTensorCollector(
            legacy,
            public_mask_provider=_NoopPublicMask(),
            policy=_RecurrentNoopPolicy(),
        )


def test_production_collect_loop_has_no_explicit_host_tensor_sync() -> None:
    source = inspect.getsource(SimpleTensorCollector.collect)
    for forbidden in (".item(", ".cpu(", ".tolist("):
        assert forbidden not in source
