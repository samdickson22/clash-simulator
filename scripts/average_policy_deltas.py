# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
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


def _load_checkpoint(path: Path) -> dict[str, Any]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict):
        raise TypeError(f"checkpoint is not a mapping: {path}")
    for field in ("format_version", "token_names", "model_config", "model_state_dict"):
        if field not in payload:
            raise ValueError(f"checkpoint lacks {field}: {path}")
    return payload


def _compatible(reference: dict[str, Any], candidate: dict[str, Any]) -> None:
    for field in ("format_version", "token_names"):
        if reference[field] != candidate[field]:
            raise ValueError(f"checkpoint {field} values differ")
    if PolicyConfig.from_dict(reference["model_config"]) != PolicyConfig.from_dict(
        candidate["model_config"]
    ):
        raise ValueError("checkpoint model_config values differ")
    if reference["model_state_dict"].keys() != candidate["model_state_dict"].keys():
        raise ValueError("checkpoint parameter names differ")


def average_policy_deltas(
    *,
    parent_path: Path,
    candidate_paths: list[Path],
    alpha: float,
) -> dict[str, Any]:
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be between zero and one")
    resolved_candidates = sorted({path.resolve() for path in candidate_paths}, key=str)
    if len(resolved_candidates) < 2:
        raise ValueError("at least two unique candidate checkpoints are required")
    parent_path = parent_path.resolve()
    parent = _load_checkpoint(parent_path)
    candidates = [_load_checkpoint(path) for path in resolved_candidates]
    for candidate in candidates:
        _compatible(parent, candidate)

    parent_state = parent["model_state_dict"]
    averaged_state: dict[str, torch.Tensor] = {}
    for name, parent_value in parent_state.items():
        candidate_values = [candidate["model_state_dict"][name] for candidate in candidates]
        if any(value.shape != parent_value.shape for value in candidate_values):
            raise ValueError(f"checkpoint parameter shape differs for {name}")
        if parent_value.is_floating_point():
            mean_delta = torch.zeros_like(parent_value)
            for value in candidate_values:
                if value.dtype != parent_value.dtype or not value.is_floating_point():
                    raise ValueError(f"checkpoint parameter dtype differs for {name}")
                mean_delta.add_(value - parent_value)
            mean_delta.div_(len(candidate_values))
            averaged_state[name] = parent_value + alpha * mean_delta
        elif all(torch.equal(value, parent_value) for value in candidate_values):
            averaged_state[name] = parent_value.clone()
        else:
            raise ValueError(f"non-floating checkpoint parameter differs for {name}")

    payload = dict(parent)
    payload["model_state_dict"] = averaged_state
    payload.pop("optimizer_state_dict", None)
    payload["policy_delta_ensemble"] = {
        "schema": "equal-weight-policy-delta-ensemble-v1",
        "alpha": alpha,
        "parent": str(parent_path),
        "parent_sha256": file_sha256(parent_path),
        "sources": [
            {"path": str(path), "sha256": file_sha256(path)}
            for path in resolved_candidates
        ],
        "weights": [1.0 / len(resolved_candidates)] * len(resolved_candidates),
    }
    return payload


def save_payload(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    if path.exists():
        raise FileExistsError(f"refusing to overwrite checkpoint: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary)
    try:
        torch.save(payload, temporary_path)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Average independent policy deltas relative to one parent"
    )
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--candidate", action="append", required=True, type=Path)
    parser.add_argument("--alpha", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = resolve_path(args.output)
    payload = average_policy_deltas(
        parent_path=resolve_path(args.parent, must_exist=True),
        candidate_paths=[resolve_path(path, must_exist=True) for path in args.candidate],
        alpha=args.alpha,
    )
    save_payload(output, payload)
    print(
        {
            "output": str(output),
            "output_sha256": file_sha256(output),
            **payload["policy_delta_ensemble"],
        }
    )


if __name__ == "__main__":
    main()
