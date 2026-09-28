from __future__ import annotations

from pathlib import Path

import pytest
import torch

from scripts.compose_play_hazard_checkpoint import compose


def _checkpoint(
    path: Path,
    *,
    hazard: float,
    memory: float,
    tokens: tuple[str, ...] = ("<padding>",),
    explicit_adapter_defaults: bool = False,
) -> None:
    model_config = {
        "num_tokens": 1,
        "max_entities": 4,
        "play_hazard_enabled": True,
        "hierarchical_mode_gate_enabled": True,
        "deterministic_hierarchy": "hazard",
        "memory_kind": "structured",
        "memory_size": 8,
    }
    if explicit_adapter_defaults:
        model_config.update(
            {
                "play_hazard_adapter_size": 0,
                "play_hazard_adapter_enemy_y_gate": 1.0,
                "play_hazard_adapter_gain": 1.0,
            }
        )
    torch.save(
        {
            "format_version": 2,
            "model_type": "entity_spatial_recurrent",
            "model_config": model_config,
            "token_names": tokens,
            "model_state_dict": {
                "memory.weight": torch.full((2, 2), memory),
                "play_hazard_head.0.weight": torch.full((2, 2), hazard),
                "play_hazard_head.0.bias": torch.full((2,), hazard),
                "play_hazard_head.2.weight": torch.full((1, 2), hazard),
                "play_hazard_head.2.bias": torch.full((1,), hazard),
            },
            "optimizer_state_dict": {"state": {1: {"step": 3}}},
            "update": 20,
        },
        path,
    )


def test_compose_copies_only_hazard_head_and_removes_optimizer(tmp_path: Path) -> None:
    body = tmp_path / "body.pt"
    donor = tmp_path / "donor.pt"
    output = tmp_path / "composed.pt"
    _checkpoint(body, hazard=20.0, memory=2.0)
    _checkpoint(donor, hazard=10.0, memory=1.0)

    result = compose(body=body, hazard_donor=donor, output=output)
    payload = torch.load(output, map_location="cpu", weights_only=False)

    assert torch.equal(
        payload["model_state_dict"]["memory.weight"], torch.full((2, 2), 2.0)
    )
    for key in result["copied_parameter_keys"]:
        assert torch.equal(
            payload["model_state_dict"][key],
            torch.load(donor, map_location="cpu", weights_only=False)[
                "model_state_dict"
            ][key],
        )
    assert "optimizer_state_dict" not in payload
    assert payload["posthoc_composition"]["evaluation_only"] is True
    assert output.with_suffix(".pt.json").is_file()


def test_compose_accepts_explicit_default_equivalent_config(tmp_path: Path) -> None:
    body = tmp_path / "body.pt"
    donor = tmp_path / "donor.pt"
    output = tmp_path / "composed.pt"
    _checkpoint(
        body,
        hazard=20.0,
        memory=2.0,
        explicit_adapter_defaults=True,
    )
    _checkpoint(donor, hazard=10.0, memory=1.0)

    compose(body=body, hazard_donor=donor, output=output)

    assert output.is_file()


def test_compose_rejects_vocab_mismatch_and_existing_output(tmp_path: Path) -> None:
    body = tmp_path / "body.pt"
    donor = tmp_path / "donor.pt"
    output = tmp_path / "composed.pt"
    _checkpoint(body, hazard=20.0, memory=2.0)
    _checkpoint(donor, hazard=10.0, memory=1.0, tokens=("other",))

    with pytest.raises(ValueError, match="token_names differ"):
        compose(body=body, hazard_donor=donor, output=output)

    output.touch()
    with pytest.raises(FileExistsError):
        compose(body=body, hazard_donor=body, output=output)
