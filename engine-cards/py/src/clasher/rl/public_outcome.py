from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from torch import Tensor, nn


class PublicOutcomeHead(nn.Module):
    """Small terminal-outcome model over the policy's public recurrent features."""

    def __init__(self, input_size: int, kind: str) -> None:
        super().__init__()
        self.network: nn.Module
        if kind == "linear":
            self.network = nn.Linear(input_size, 1)
        elif kind == "mlp":
            self.network = nn.Sequential(
                nn.LayerNorm(input_size),
                nn.Linear(input_size, 128),
                nn.GELU(),
                nn.Linear(128, 1),
            )
        else:
            raise ValueError(f"unknown public outcome head kind {kind!r}")

    def forward(self, features: Tensor) -> Tensor:
        result: Tensor = self.network(features).squeeze(-1)
        return result


@dataclass(frozen=True)
class LoadedPublicOutcomeHead:
    head: PublicOutcomeHead
    input_size: int
    kind: str
    source_checkpoint: str

    @torch.no_grad()
    def probability_p0(self, features_0: Tensor, features_1: Tensor) -> Tensor:
        """Return an exactly zero-sum probability from paired public views."""
        if features_0.shape != features_1.shape:
            raise ValueError("paired public outcome features must have matching shapes")
        if features_0.shape[-1] != self.input_size:
            raise ValueError(
                "public outcome feature width does not match its checkpoint"
            )
        logit_0 = self.head(features_0)
        logit_1 = self.head(features_1)
        return torch.sigmoid(0.5 * (logit_0 - logit_1))


def load_public_outcome_head(
    checkpoint_path: Path,
    *,
    device: torch.device,
) -> LoadedPublicOutcomeHead:
    payload: dict[str, Any] = torch.load(
        checkpoint_path,
        map_location=device,
        weights_only=False,
    )
    if int(payload.get("schema_version", 0)) != 1:
        raise ValueError("unsupported public outcome checkpoint schema")
    kind = str(payload["kind"])
    input_size = int(payload["input_size"])
    head = PublicOutcomeHead(input_size, kind).to(device)
    head.load_state_dict(payload["state_dict"])
    head.eval()
    return LoadedPublicOutcomeHead(
        head=head,
        input_size=input_size,
        kind=kind,
        source_checkpoint=str(payload["source_checkpoint"]),
    )
