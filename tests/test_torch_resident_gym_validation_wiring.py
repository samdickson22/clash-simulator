from __future__ import annotations

import random
from collections import deque

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.policy_validation import (
    PROJECTED_GYM_TRANSITION_PROFILE,
    PUBLIC_ACTION_MASK_CONTRACT_V2,
    compare_projected_gym_transitions,
)
from clasher.torch_sim.resident_differential import (
    ResidentEpisodeDifferential,
    ResidentValidationProfile,
)
from clasher.torch_sim.resident_selfplay import (
    SIMULATOR_EXACT_ACTION_MASK_PROFILE,
    ResidentGymTransitionInputs,
    ResidentGymValidationError,
    TensorResidentSelfPlay,
)


def _safe_battle(seed: int) -> BattleState:
    battle = BattleState(rng=random.Random(seed))
    for player in battle.players:
        player.deck = []
        player.hand = [None, None, None, None]
        player.cycle_queue = deque()
        player.elixir = 5.0
    return battle


def _catalog() -> TensorCardCatalog:
    battle = BattleState()
    return TensorCardCatalog.compile(battle.card_loader, ["Knight"])


def _history(
    batch: int,
    *,
    public_action_masks: torch.Tensor | None = None,
    public_action_mask_contract_version: int | None = None,
) -> ResidentGymTransitionInputs:
    return ResidentGymTransitionInputs(
        previous_actions=torch.full(
            (batch, 2), NO_OP_ACTION, dtype=torch.int64
        ),
        previous_rewards=torch.zeros((batch, 2), dtype=torch.float32),
        episode_starts=torch.ones((batch, 2), dtype=torch.bool),
        recurrent_inputs={
            "hidden": torch.zeros((batch, 2, 4), dtype=torch.float32)
        },
        public_action_masks=public_action_masks,
        public_action_mask_contract_version=public_action_mask_contract_version,
    )


def test_validation_is_opt_in_and_strict_oracle_default_is_unchanged() -> None:
    differential = ResidentEpisodeDifferential()
    assert differential.validation_profile is ResidentValidationProfile.STRICT_ORACLE

    bridge = TensorResidentSelfPlay.from_battles(
        [_safe_battle(96_001)],
        decision_interval_ticks=1,
        max_ticks=1,
        max_entities=16,
        max_objects=16,
        catalog=_catalog(),
    )
    result = bridge.step(torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64))

    assert bridge.validation_profile is None
    assert result.validation is None


def test_projected_profile_emits_native_admission_and_comparator_boundary() -> None:
    seen: list[tuple[str, list[int]]] = []

    def validator(transition, metadata):  # type: ignore[no-untyped-def]
        seen.append((metadata.profile, metadata.native_ticks.tolist()))
        return compare_projected_gym_transitions(transition, transition)

    bridge = TensorResidentSelfPlay.from_battles(
        [_safe_battle(96_101), _safe_battle(96_102)],
        decision_interval_ticks=2,
        max_ticks=4,
        max_entities=16,
        max_objects=16,
        catalog=_catalog(),
        structured_builder=StructuredObservationBuilder(
            card_vocab=[], max_entities=16
        ),
        include_privileged_critic=True,
        validation_profile=PROJECTED_GYM_TRANSITION_PROFILE,
        transition_validator=validator,
    )

    public_masks = torch.ones((2, 2, 5), dtype=torch.bool)
    result = bridge.step(
        torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64),
        validation_inputs=_history(
            2,
            public_action_masks=public_masks,
            public_action_mask_contract_version=PUBLIC_ACTION_MASK_CONTRACT_V2,
        ),
    )

    assert result.validation is not None
    boundary = result.validation
    assert boundary.metadata.profile == PROJECTED_GYM_TRANSITION_PROFILE
    assert (
        boundary.metadata.public_action_mask_contract_version
        == PUBLIC_ACTION_MASK_CONTRACT_V2
    )
    assert (
        boundary.metadata.simulator_action_mask_profile
        == SIMULATOR_EXACT_ACTION_MASK_PROFILE
    )
    assert boundary.metadata.requested_native_ticks.tolist() == [2, 2]
    assert boundary.metadata.native_ticks.tolist() == [2, 2]
    assert boundary.metadata.fallback_rows == ()
    assert boundary.metadata.all_rows_admitted
    assert boundary.transition.public_action_mask_contract_version == 2
    assert boundary.transition.public_action_masks is public_masks
    assert boundary.transition.public_action_masks is not result.action_masks
    assert boundary.transition.actor is result.public.structured
    assert boundary.transition.critic is result.privileged_critic
    assert boundary.comparison is not None and boundary.comparison.passed
    assert seen == [(PROJECTED_GYM_TRANSITION_PROFILE, [2, 2])]


def test_simulator_legal_masks_are_not_implicitly_labeled_public_mask_v2() -> None:
    bridge = TensorResidentSelfPlay.from_battles(
        [_safe_battle(96_151)],
        decision_interval_ticks=1,
        max_ticks=1,
        max_entities=16,
        max_objects=16,
        catalog=_catalog(),
        validation_profile=PROJECTED_GYM_TRANSITION_PROFILE,
    )

    result = bridge.step(
        torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64),
        validation_inputs=_history(1),
    )

    assert result.validation is not None
    assert result.validation.transition.public_action_masks is None
    assert (
        result.validation.transition.public_action_mask_contract_version is None
    )
    assert result.action_masks.shape[0:2] == (1, 2)


def test_projected_profile_requires_history_before_any_mutation() -> None:
    bridge = TensorResidentSelfPlay.from_battles(
        [_safe_battle(96_201)],
        decision_interval_ticks=2,
        max_entities=16,
        max_objects=16,
        catalog=_catalog(),
        validation_profile=PROJECTED_GYM_TRANSITION_PROFILE,
    )
    tick_before = bridge.engine.runtime.battle.tick.clone()
    rng_before = bridge.engine.runtime.battle.rng.python_state(0)

    with pytest.raises(
        ResidentGymValidationError, match="explicit policy history inputs"
    ):
        bridge.step(torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64))

    assert torch.equal(bridge.engine.runtime.battle.tick, tick_before)
    assert bridge.engine.runtime.battle.rng.python_state(0) == rng_before


def test_projected_profile_rejects_fallback_row_before_safe_rows_mutate() -> None:
    safe = _safe_battle(96_301)
    unsupported = BattleState(rng=random.Random(96_302))
    bridge = TensorResidentSelfPlay.from_battles(
        [safe, unsupported],
        decision_interval_ticks=2,
        max_entities=32,
        max_objects=32,
        validation_profile=PROJECTED_GYM_TRANSITION_PROFILE,
    )
    ticks_before = bridge.engine.runtime.battle.tick.clone()
    rng_before = tuple(
        bridge.engine.runtime.battle.rng.python_state(row) for row in range(2)
    )

    with pytest.raises(
        ResidentGymValidationError,
        match=r"zero fallback before mutation; rejected rows: \(1,\)",
    ):
        bridge.step(
            torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64),
            validation_inputs=_history(2),
        )

    assert torch.equal(bridge.engine.runtime.battle.tick, ticks_before)
    assert tuple(
        bridge.engine.runtime.battle.rng.python_state(row) for row in range(2)
    ) == rng_before


def test_validator_cannot_be_configured_without_explicit_profile() -> None:
    with pytest.raises(ValueError, match="requires an explicit validation_profile"):
        TensorResidentSelfPlay.from_battles(
            [_safe_battle(96_401)],
            max_entities=16,
            max_objects=16,
            catalog=_catalog(),
            transition_validator=lambda _transition, _metadata: None,
        )
