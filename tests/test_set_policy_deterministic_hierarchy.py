from __future__ import annotations

from pathlib import Path

import torch

from scripts.set_policy_deterministic_hierarchy import (
    set_deterministic_hierarchy,
)


def test_hierarchy_checkpoint_edit_preserves_every_state_tensor(
    tmp_path: Path,
) -> None:
    source = Path(
        "checkpoints/tv_raw1000_spatial_value_rl_seed1044801/"
        "policy_v2_update_000040.pt"
    ).resolve()
    output = tmp_path / "play-gate.pt"

    result = set_deterministic_hierarchy(
        source=source,
        output=output,
        hierarchy="play-gate",
    )

    before = torch.load(source, map_location="cpu", weights_only=False)
    after = torch.load(output, map_location="cpu", weights_only=False)
    assert after["model_config"]["deterministic_hierarchy"] == "play-gate"
    assert result["stochastic_distribution_changed"] is False
    assert "optimizer_state_dict" not in after
    assert before["model_state_dict"].keys() == after["model_state_dict"].keys()
    for name, tensor in before["model_state_dict"].items():
        torch.testing.assert_close(tensor, after["model_state_dict"][name])
