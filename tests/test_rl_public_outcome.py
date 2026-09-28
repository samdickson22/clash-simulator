from __future__ import annotations

from pathlib import Path

import torch

from clasher.rl.public_outcome import (
    LoadedPublicOutcomeHead,
    PublicOutcomeHead,
    load_public_outcome_head,
)


def test_paired_public_outcome_probability_is_exactly_zero_sum() -> None:
    head = PublicOutcomeHead(1, "linear")
    with torch.no_grad():
        head.network.weight.fill_(2.0)
        head.network.bias.fill_(3.0)
    loaded = LoadedPublicOutcomeHead(
        head=head,
        input_size=1,
        kind="linear",
        source_checkpoint="policy.pt",
    )
    first = torch.tensor([[1.0], [-2.0]])
    second = torch.tensor([[-1.0], [2.0]])

    probability = loaded.probability_p0(first, second)
    reverse = loaded.probability_p0(second, first)

    torch.testing.assert_close(probability + reverse, torch.ones_like(probability))
    # The learned common bias cancels when the two public perspectives are paired.
    torch.testing.assert_close(probability, torch.sigmoid(torch.tensor([2.0, -4.0])))


def test_public_outcome_checkpoint_round_trip(tmp_path: Path) -> None:
    head = PublicOutcomeHead(3, "mlp")
    path = tmp_path / "outcome.pt"
    torch.save(
        {
            "schema_version": 1,
            "kind": "mlp",
            "input_size": 3,
            "source_checkpoint": "policy.pt",
            "state_dict": head.state_dict(),
        },
        path,
    )

    loaded = load_public_outcome_head(path, device=torch.device("cpu"))

    assert loaded.kind == "mlp"
    assert loaded.input_size == 3
    assert loaded.source_checkpoint == "policy.pt"
