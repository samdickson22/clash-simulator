from __future__ import annotations

from pathlib import Path

import pytest
import torch

from scripts.convert_hog26_hazard_to_playgate import (
    CONVERSION_SCHEMA,
    convert_payload,
)


def test_conversion_removes_hazard_parameters_and_preserves_other_state() -> None:
    payload = {
        "model_config": {
            "deterministic_hierarchy": "hazard",
            "hierarchical_mode_gate_enabled": True,
            "play_hazard_enabled": True,
            "play_hazard_adapter_size": 16,
            "play_hazard_adapter_enemy_y_gate": 0.4,
            "play_hazard_adapter_gain": 0.5,
        },
        "model_state_dict": {
            "actor.weight": torch.ones(2),
            "play_hazard_head.0.weight": torch.ones(1),
            "play_hazard_adapter.0.weight": torch.ones(1),
        },
        "optimizer_state_dict": {"unsafe": True},
    }

    converted = convert_payload(
        payload,
        source=Path("parent.pt"),
        source_sha256="abc",
    )

    assert converted["model_config"]["deterministic_hierarchy"] == "play-gate"
    assert converted["model_config"]["play_hazard_enabled"] is False
    assert converted["model_config"]["play_hazard_adapter_size"] == 0
    assert set(converted["model_state_dict"]) == {"actor.weight"}
    assert torch.equal(converted["model_state_dict"]["actor.weight"], torch.ones(2))
    assert "optimizer_state_dict" not in converted
    assert converted["architecture_conversion"]["schema"] == CONVERSION_SCHEMA
    assert payload["model_config"]["deterministic_hierarchy"] == "hazard"


def test_conversion_rejects_non_hazard_checkpoint() -> None:
    with pytest.raises(ValueError, match="not hazard-gated"):
        convert_payload(
            {
                "model_config": {
                    "deterministic_hierarchy": "play-gate",
                    "hierarchical_mode_gate_enabled": True,
                    "play_hazard_enabled": False,
                },
                "model_state_dict": {},
            },
            source=Path("parent.pt"),
            source_sha256="abc",
        )


def test_conversion_can_target_internal_event_accumulation() -> None:
    payload = {
        "model_config": {
            "deterministic_hierarchy": "hazard",
            "hierarchical_mode_gate_enabled": True,
            "play_hazard_enabled": True,
            "play_hazard_adapter_size": 0,
        },
        "model_state_dict": {
            "actor.weight": torch.ones(2),
            "play_hazard_head.0.weight": torch.ones(1),
        },
    }
    converted = convert_payload(
        payload,
        source=Path("parent.pt"),
        source_sha256="abc",
        target_hierarchy="event",
    )
    assert converted["model_config"]["deterministic_hierarchy"] == "event"
    assert converted["model_config"]["play_hazard_enabled"] is False
