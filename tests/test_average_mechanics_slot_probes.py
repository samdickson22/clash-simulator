from __future__ import annotations

from pathlib import Path

import pytest
import torch

from scripts.average_mechanics_slot_probes import average_probes


def _probe(path: Path, weight: list[list[float]], *, semantics: int = 1) -> None:
    torch.save(
        {
            "schema_version": 1,
            "semantics_version": semantics,
            "hidden_size": 0,
            "state_dict": {"state_query.weight": torch.tensor(weight)},
            "token_names": ("<pad>", "Knight"),
        },
        path,
    )


def test_average_probes_is_equal_weight_and_records_sources(tmp_path: Path) -> None:
    first = tmp_path / "first.pt"
    second = tmp_path / "second.pt"
    output = tmp_path / "average.pt"
    _probe(first, [[1.0, 3.0]])
    _probe(second, [[3.0, 7.0]])

    payload = average_probes(sources=[second, first], output=output)
    saved = torch.load(output, map_location="cpu", weights_only=False)

    torch.testing.assert_close(
        saved["state_dict"]["state_query.weight"], torch.tensor([[2.0, 5.0]])
    )
    assert saved["ensemble"] == payload["ensemble"]
    assert saved["ensemble"]["weights"] == [0.5, 0.5]
    assert [Path(row["path"]).name for row in saved["ensemble"]["sources"]] == [
        "first.pt",
        "second.pt",
    ]
    assert all(len(row["sha256"]) == 64 for row in saved["ensemble"]["sources"])


def test_average_probes_rejects_incompatible_architectures(tmp_path: Path) -> None:
    first = tmp_path / "first.pt"
    second = tmp_path / "second.pt"
    _probe(first, [[1.0, 3.0]], semantics=1)
    _probe(second, [[3.0, 7.0]], semantics=2)

    with pytest.raises(ValueError, match="architecture/vocabulary compatible"):
        average_probes(
            sources=[first, second],
            output=tmp_path / "average.pt",
        )


def test_average_probes_refuses_to_overwrite(tmp_path: Path) -> None:
    first = tmp_path / "first.pt"
    second = tmp_path / "second.pt"
    output = tmp_path / "average.pt"
    _probe(first, [[1.0, 3.0]])
    _probe(second, [[3.0, 7.0]])
    output.write_bytes(b"owned")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        average_probes(sources=[first, second], output=output)
