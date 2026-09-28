from __future__ import annotations

# mypy: disable-error-code="import-untyped"

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import torch

from clasher.paths import resolve_path
from clasher.rl.model import PolicyConfig


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def interpolate_policy_payloads(
    parent: dict[str, Any],
    candidate: dict[str, Any],
    *,
    alpha: float,
    allow_extrapolation: bool = False,
) -> dict[str, Any]:
    if alpha < 0.0 or (alpha > 1.0 and not allow_extrapolation):
        raise ValueError(
            "alpha must be nonnegative and at most one unless extrapolation is allowed"
        )
    for field in ("format_version", "token_names"):
        if parent.get(field) != candidate.get(field):
            raise ValueError(f"checkpoint {field} values differ")
    parent_config = parent.get("model_config")
    candidate_config = candidate.get("model_config")
    try:
        configs_match = PolicyConfig.from_dict(parent_config) == PolicyConfig.from_dict(
            candidate_config
        )
    except (KeyError, TypeError, ValueError):
        configs_match = parent_config == candidate_config
    if not configs_match:
        raise ValueError("checkpoint model_config values differ")
    parent_state = parent["model_state_dict"]
    candidate_state = candidate["model_state_dict"]
    if parent_state.keys() != candidate_state.keys():
        raise ValueError("checkpoint parameter names differ")
    mixed_state: dict[str, torch.Tensor] = {}
    for name, parent_value in parent_state.items():
        candidate_value = candidate_state[name]
        if parent_value.shape != candidate_value.shape:
            raise ValueError(f"checkpoint parameter shape differs for {name}")
        if parent_value.is_floating_point():
            mixed_state[name] = torch.lerp(parent_value, candidate_value, alpha)
        elif torch.equal(parent_value, candidate_value):
            mixed_state[name] = parent_value.clone()
        else:
            raise ValueError(f"non-floating checkpoint parameter differs for {name}")
    payload = dict(candidate)
    payload["model_state_dict"] = mixed_state
    payload.pop("optimizer_state_dict", None)
    payload["interpolation"] = {
        "schema_version": 1,
        "alpha": alpha,
        "parent_update": int(parent.get("update", 0)),
        "candidate_update": int(candidate.get("update", 0)),
    }
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interpolate compatible V2 policy checkpoints in weight space"
    )
    parser.add_argument("--parent", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--allow-extrapolation", action="store_true")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    parent_path = resolve_path(args.parent, must_exist=True)
    candidate_path = resolve_path(args.candidate, must_exist=True)
    output_path = resolve_path(args.output)
    parent = torch.load(parent_path, map_location="cpu", weights_only=False)
    candidate = torch.load(candidate_path, map_location="cpu", weights_only=False)
    payload = interpolate_policy_payloads(
        parent,
        candidate,
        alpha=args.alpha,
        allow_extrapolation=args.allow_extrapolation,
    )
    payload["interpolation"].update(
        {
            "parent": str(parent_path),
            "parent_sha256": file_sha256(parent_path),
            "candidate": str(candidate_path),
            "candidate_sha256": file_sha256(candidate_path),
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, output_path)
    print(
        json.dumps(
            {
                "output": str(output_path),
                "output_sha256": file_sha256(output_path),
                **payload["interpolation"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
