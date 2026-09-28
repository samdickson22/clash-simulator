from __future__ import annotations

from pathlib import Path

import torch

from clasher.rl.model import PolicyConfig
from scripts.set_structured_clock_horizon import set_structured_clock_horizon


def test_set_structured_clock_horizon_changes_config_only(tmp_path: Path) -> None:
    source = tmp_path / "source.pt"
    output = tmp_path / "output.pt"
    config = PolicyConfig(
        num_tokens=3,
        max_entities=4,
        memory_kind="structured",
        memory_size=16,
        structured_clock_horizon_steps=750,
    )
    state = {"weight": torch.arange(5, dtype=torch.float32)}
    torch.save(
        {
            "format_version": 2,
            "model_config": config.to_dict(),
            "model_state_dict": state,
            "optimizer_state_dict": {"discard": True},
        },
        source,
    )

    report = set_structured_clock_horizon(
        source=source, output=output, horizon_steps=1500
    )
    result = torch.load(output, map_location="cpu", weights_only=False)

    assert result["model_config"]["structured_clock_horizon_steps"] == 1500
    torch.testing.assert_close(
        result["model_state_dict"]["weight"], state["weight"]
    )
    assert "optimizer_state_dict" not in result
    assert report["state_tensors_changed"] == 0

