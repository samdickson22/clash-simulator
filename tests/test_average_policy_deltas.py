from pathlib import Path

import pytest
import torch

from scripts.average_policy_deltas import average_policy_deltas, save_payload


def _checkpoint(path: Path, *, weight: float, token: str = "Knight") -> Path:
    torch.save(
        {
            "format_version": 2,
            "token_names": ["<pad>", token],
            "model_config": {"num_tokens": 2, "max_entities": 4},
            "model_state_dict": {
                "weight": torch.tensor([weight, 2.0 * weight]),
                "counter": torch.tensor(7, dtype=torch.long),
            },
            "optimizer_state_dict": {"unsafe": True},
            "update": 20,
        },
        path,
    )
    return path


def test_average_policy_deltas_averages_relative_updates_and_scales(tmp_path: Path):
    parent = _checkpoint(tmp_path / "parent.pt", weight=10.0)
    first = _checkpoint(tmp_path / "first.pt", weight=12.0)
    second = _checkpoint(tmp_path / "second.pt", weight=14.0)

    payload = average_policy_deltas(
        parent_path=parent,
        candidate_paths=[second, first],
        alpha=0.5,
    )

    torch.testing.assert_close(
        payload["model_state_dict"]["weight"], torch.tensor([11.5, 23.0])
    )
    assert payload["model_state_dict"]["counter"].item() == 7
    assert "optimizer_state_dict" not in payload
    assert payload["policy_delta_ensemble"]["weights"] == [0.5, 0.5]
    assert [Path(row["path"]).name for row in payload["policy_delta_ensemble"]["sources"]] == [
        "first.pt",
        "second.pt",
    ]


def test_average_policy_deltas_rejects_incompatible_or_duplicate_sources(
    tmp_path: Path,
):
    parent = _checkpoint(tmp_path / "parent.pt", weight=10.0)
    first = _checkpoint(tmp_path / "first.pt", weight=12.0)
    incompatible = _checkpoint(
        tmp_path / "incompatible.pt", weight=14.0, token="Archers"
    )

    with pytest.raises(ValueError, match="at least two unique"):
        average_policy_deltas(
            parent_path=parent,
            candidate_paths=[first, first],
            alpha=1.0,
        )
    with pytest.raises(ValueError, match="token_names"):
        average_policy_deltas(
            parent_path=parent,
            candidate_paths=[first, incompatible],
            alpha=1.0,
        )


def test_save_payload_is_atomic_and_refuses_overwrite(tmp_path: Path):
    output = tmp_path / "ensemble.pt"
    save_payload(output, {"value": torch.tensor(3.0)})
    assert torch.load(output, weights_only=False)["value"].item() == 3.0
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        save_payload(output, {"value": torch.tensor(4.0)})
