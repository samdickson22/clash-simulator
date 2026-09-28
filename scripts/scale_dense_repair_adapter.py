"""Scale an additive dense repair adapter without changing the base policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import torch

from clasher.paths import resolve_path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def scale_dense_repair_payload(
    payload: dict[str, Any],
    *,
    alpha: float,
    prefix: str = "repair_adapter",
) -> dict[str, Any]:
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be between zero and one")
    state = dict(payload["model_state_dict"])
    output_names = (f"{prefix}.2.weight", f"{prefix}.2.bias")
    if not all(name in state for name in output_names):
        raise ValueError("checkpoint does not contain the expected dense repair adapter")
    for name in output_names:
        state[name] = state[name] * alpha
    scaled = dict(payload)
    scaled["model_state_dict"] = state
    scaled.pop("optimizer_state_dict", None)
    scaled["repair_adapter_scale"] = {
        "schema_version": 1,
        "alpha": alpha,
        "prefix": prefix,
    }
    return scaled


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scale only the output layer of a dense repair adapter"
    )
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--stage-index", type=int)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checkpoint_path = resolve_path(args.checkpoint, must_exist=True)
    output_path = resolve_path(args.output)
    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    prefix = (
        "repair_adapter"
        if args.stage_index is None
        else f"repair_stages.{args.stage_index}"
    )
    scaled = scale_dense_repair_payload(payload, alpha=args.alpha, prefix=prefix)
    scaled["repair_adapter_scale"].update(
        {
            "source": str(checkpoint_path),
            "source_sha256": file_sha256(checkpoint_path),
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(scaled, output_path)
    print(
        json.dumps(
            {
                "output": str(output_path),
                "output_sha256": file_sha256(output_path),
                **scaled["repair_adapter_scale"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
