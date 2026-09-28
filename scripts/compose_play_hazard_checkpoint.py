#!/usr/bin/env python3
"""Compose an evaluation checkpoint from a policy body and hazard-head donor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import torch

from clasher.rl.model import PolicyConfig

HAZARD_PREFIX = "play_hazard_head."


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict):
        raise TypeError("checkpoint must be a dictionary")
    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("checkpoint is not policy format version 2")
    if not isinstance(payload.get("model_config"), dict):
        raise TypeError("checkpoint model_config must be a dictionary")
    if not isinstance(payload.get("model_state_dict"), dict):
        raise TypeError("checkpoint model_state_dict must be a dictionary")
    return payload


def _normalized_model_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Materialize dataclass defaults before comparing checkpoint configs."""

    config = payload["model_config"]
    assert isinstance(config, dict)
    return PolicyConfig.from_dict(config).to_dict()


def compose(*, body: Path, hazard_donor: Path, output: Path) -> dict[str, Any]:
    """Copy only the complete play-hazard head from donor into body."""

    if output.exists():
        raise FileExistsError(output)
    body_payload = _load_checkpoint(body)
    donor_payload = _load_checkpoint(hazard_donor)
    for field in ("model_type", "token_names"):
        if body_payload.get(field) != donor_payload.get(field):
            raise ValueError(f"body and hazard donor {field} differ")
    if _normalized_model_config(body_payload) != _normalized_model_config(
        donor_payload
    ):
        raise ValueError("body and hazard donor model_config differ")

    body_state = body_payload["model_state_dict"]
    donor_state = donor_payload["model_state_dict"]
    body_hazard = {key for key in body_state if key.startswith(HAZARD_PREFIX)}
    donor_hazard = {key for key in donor_state if key.startswith(HAZARD_PREFIX)}
    if not body_hazard or body_hazard != donor_hazard:
        raise ValueError("body and donor do not have the same nonempty hazard head")
    for key in sorted(body_hazard):
        body_value = body_state[key]
        donor_value = donor_state[key]
        if not isinstance(body_value, torch.Tensor) or not isinstance(
            donor_value, torch.Tensor
        ):
            raise TypeError(f"hazard parameter {key} is not a tensor")
        if (
            body_value.shape != donor_value.shape
            or body_value.dtype != donor_value.dtype
        ):
            raise ValueError(f"hazard parameter {key} differs in shape or dtype")

    composed = dict(body_payload)
    composed_state = dict(body_state)
    for key in sorted(body_hazard):
        composed_state[key] = donor_state[key].detach().clone()
    composed["model_state_dict"] = composed_state
    # The body's optimizer moments no longer correspond to the composed weights.
    composed.pop("optimizer_state_dict", None)
    body_sha = _sha256(body)
    donor_sha = _sha256(hazard_donor)
    composed["posthoc_composition"] = {
        "schema": "clasher.play_hazard_head_composition.v1",
        "body_checkpoint": str(body.resolve()),
        "body_sha256": body_sha,
        "hazard_donor_checkpoint": str(hazard_donor.resolve()),
        "hazard_donor_sha256": donor_sha,
        "copied_parameter_keys": sorted(body_hazard),
        "evaluation_only": True,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    torch.save(composed, temporary)
    os.replace(temporary, output)
    result = {
        "schema": "clasher.play_hazard_head_composition.v1",
        "body_checkpoint": str(body.resolve()),
        "body_sha256": body_sha,
        "hazard_donor_checkpoint": str(hazard_donor.resolve()),
        "hazard_donor_sha256": donor_sha,
        "output_checkpoint": str(output.resolve()),
        "output_sha256": _sha256(output),
        "copied_parameter_keys": sorted(body_hazard),
        "evaluation_only": True,
    }
    manifest = output.with_suffix(output.suffix + ".json")
    manifest.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--body", required=True, type=Path)
    parser.add_argument("--hazard-donor", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            compose(
                body=args.body,
                hazard_donor=args.hazard_donor,
                output=args.output,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
