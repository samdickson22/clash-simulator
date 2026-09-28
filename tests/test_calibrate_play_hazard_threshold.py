from __future__ import annotations

from pathlib import Path

import pytest
import torch

from scripts.calibrate_play_hazard_threshold import calibrate


def _checkpoint(path: Path, *, hazard: bool = True) -> None:
    torch.save(
        {
            "format_version": 2,
            "model_config": {
                "play_hazard_enabled": hazard,
                "play_hazard_threshold": 0.5,
            },
            "model_state_dict": {"weight": torch.arange(4)},
            "optimizer_state_dict": {"state": {1: {"step": 3}}},
        },
        path,
    )


def test_calibrate_changes_only_threshold_and_strips_optimizer(tmp_path: Path) -> None:
    source = tmp_path / "source.pt"
    _checkpoint(source)
    manifest = calibrate(
        source=source,
        output_root=tmp_path / "outputs",
        thresholds=[0.2, 0.3],
    )

    assert [row["threshold"] for row in manifest["outputs"]] == [0.2, 0.3]
    for row in manifest["outputs"]:
        payload = torch.load(row["checkpoint"], map_location="cpu", weights_only=False)
        assert payload["model_config"]["play_hazard_threshold"] == row["threshold"]
        assert torch.equal(payload["model_state_dict"]["weight"], torch.arange(4))
        assert "optimizer_state_dict" not in payload
        assert payload["posthoc_calibration"]["evaluation_only"] is True


def test_calibrate_rejects_invalid_or_nonhazard_sources(tmp_path: Path) -> None:
    source = tmp_path / "source.pt"
    _checkpoint(source, hazard=False)
    with pytest.raises(ValueError, match="no play-hazard"):
        calibrate(source=source, output_root=tmp_path / "out", thresholds=[0.2])
    _checkpoint(source)
    with pytest.raises(ValueError, match="finite and in"):
        calibrate(source=source, output_root=tmp_path / "out", thresholds=[1.0])
