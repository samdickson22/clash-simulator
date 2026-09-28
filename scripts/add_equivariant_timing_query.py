from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add_equivariant_timing_query(payload: dict[str, Any]) -> dict[str, Any]:
    config = PolicyConfig.from_dict(payload["model_config"])
    if not config.equivariant_slot_choice:
        raise ValueError("timing query requires equivariant slot choice")
    if config.equivariant_timing_query_enabled:
        raise ValueError("checkpoint already has an equivariant timing query")
    upgraded = PolicyConfig.from_dict(
        {
            **config.to_dict(),
            "equivariant_deterministic_timing_pool": "log-mass",
            "equivariant_timing_query_enabled": True,
        }
    )
    state = payload["model_state_dict"]
    card_stats = state.get("actor_encoder.card_stat_features")
    if not isinstance(card_stats, (np.ndarray, torch.Tensor)):
        raise TypeError("checkpoint has no actor card-stat buffer")
    model = ClasherPolicy(upgraded, card_stats)
    incompatible = model.load_state_dict(state, strict=False)
    expected = {
        "equivariant_timing_query.weight",
        "equivariant_timing_query.bias",
    }
    if incompatible.unexpected_keys or set(incompatible.missing_keys) != expected:
        raise ValueError(
            "unexpected timing-query checkpoint mismatch: "
            f"missing={sorted(incompatible.missing_keys)!r}, "
            f"unexpected={sorted(incompatible.unexpected_keys)!r}"
        )
    assert model.equivariant_timing_query is not None
    if bool(torch.count_nonzero(model.equivariant_timing_query.weight)) or bool(
        torch.count_nonzero(model.equivariant_timing_query.bias)
    ):
        raise RuntimeError("new timing query is not zero initialized")

    result = dict(payload)
    result["model_config"] = upgraded.to_dict()
    result["model_state_dict"] = model.state_dict()
    result.pop("optimizer_state_dict", None)
    result["equivariant_timing_query_upgrade"] = {
        "schema_version": 1,
        "outputs": ["play", "wait", "ability"],
        "query_is_zero_and_requires_distillation": True,
        "slot_choice_tensors_unchanged": True,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = torch.load(args.input, map_location="cpu", weights_only=False)
    result = add_equivariant_timing_query(payload)
    result["equivariant_timing_query_upgrade"] = {
        **result["equivariant_timing_query_upgrade"],
        "source_checkpoint": str(args.input.resolve()),
        "source_checkpoint_sha256": _sha256(args.input),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(result, args.output)
    print(f"output={args.output.resolve()}")
    print(f"sha256={_sha256(args.output)}")


if __name__ == "__main__":
    main()
