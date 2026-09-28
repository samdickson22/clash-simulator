#!/usr/bin/env python3
"""Create evaluation-only checkpoints with calibrated internal hazard thresholds."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import torch


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _threshold_name(threshold: float) -> str:
    return f"threshold_{threshold:.4f}".replace(".", "p")


def calibrate(
    *, source: Path, output_root: Path, thresholds: list[float]
) -> dict[str, Any]:
    if not source.is_file():
        raise FileNotFoundError(source)
    if not thresholds:
        raise ValueError("at least one threshold is required")
    if len(set(thresholds)) != len(thresholds):
        raise ValueError("thresholds must be unique")
    if any(
        not math.isfinite(threshold) or not 0.0 < threshold < 1.0
        for threshold in thresholds
    ):
        raise ValueError("thresholds must be finite and in (0, 1)")

    checkpoint = torch.load(source, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, dict):
        raise TypeError("checkpoint must be a dictionary")
    model_config = checkpoint.get("model_config")
    if not isinstance(model_config, dict):
        raise TypeError("checkpoint model_config must be a dictionary")
    if not bool(model_config.get("play_hazard_enabled", False)):
        raise ValueError("checkpoint has no play-hazard head")

    output_root.mkdir(parents=True, exist_ok=True)
    source_sha = _sha256(source)
    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        calibrated = dict(checkpoint)
        calibrated_config = dict(model_config)
        calibrated_config["play_hazard_threshold"] = threshold
        calibrated["model_config"] = calibrated_config
        calibrated.pop("optimizer_state_dict", None)
        calibrated["posthoc_calibration"] = {
            "schema": "clasher.play_hazard_threshold.v1",
            "source_checkpoint": str(source.resolve()),
            "source_sha256": source_sha,
            "threshold": threshold,
            "evaluation_only": True,
        }
        output = output_root / f"{source.stem}_{_threshold_name(threshold)}.pt"
        if output.exists():
            raise FileExistsError(output)
        temporary = output.with_suffix(output.suffix + ".tmp")
        torch.save(calibrated, temporary)
        os.replace(temporary, output)
        rows.append(
            {
                "threshold": threshold,
                "checkpoint": str(output.resolve()),
                "sha256": _sha256(output),
            }
        )

    manifest = {
        "schema": "clasher.play_hazard_threshold_sweep.v1",
        "source_checkpoint": str(source.resolve()),
        "source_sha256": source_sha,
        "outputs": rows,
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--threshold", action="append", required=True, type=float)
    args = parser.parse_args()
    print(
        json.dumps(
            calibrate(
                source=args.source,
                output_root=args.output_root,
                thresholds=args.threshold,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
