from __future__ import annotations

import pytest

from scripts.fit_public_action_value import validate_source_policy_manifest


def test_phase_stratified_manifest_is_a_supported_policy_authority() -> None:
    digest = "a" * 64
    validate_source_policy_manifest(
        {
            "schema": "clasher.hog26_phase_stratified_terminal_cf.v1",
            "structured_state_contract": "public-actor-v2-action-time-recurrence",
            "best_action_order": "outcome-crowns-tower-damage-v1",
            "query_schedule": "phase-stratified-uniform-plus-screened-overtime-v1",
            "inputs": {"policy": digest},
        },
        source_policy_sha256=digest,
    )


def test_phase_stratified_manifest_rejects_changed_contract() -> None:
    digest = "a" * 64
    with pytest.raises(ValueError, match="contract changed"):
        validate_source_policy_manifest(
            {
                "schema": "clasher.hog26_phase_stratified_terminal_cf.v1",
                "structured_state_contract": "public-actor-v1",
                "best_action_order": "outcome-crowns-tower-damage-v1",
                "query_schedule": "phase-stratified-uniform-plus-screened-overtime-v1",
                "inputs": {"policy": digest},
            },
            source_policy_sha256=digest,
        )


def test_manifest_rejects_unpinned_source_policy() -> None:
    with pytest.raises(ValueError, match="not an authority"):
        validate_source_policy_manifest(
            {
                "schema": "clasher.hog26_terminal_counterfactual_10k.v1",
                "inputs": {"policy": "b" * 64},
            },
            source_policy_sha256="a" * 64,
        )
