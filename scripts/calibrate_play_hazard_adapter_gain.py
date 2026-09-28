#!/usr/bin/env python3
"""Create evaluation-only checkpoints with calibrated hazard-adapter gain."""

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


def _gain_name(gain: float) -> str:
    return f"gain_{gain:.4f}".replace(".", "p")


def calibrate(
    *, source: Path, output_root: Path, gains: list[float]
) -> dict[str, Any]:
    if not source.is_file():
        raise FileNotFoundError(source)
    if not gains:
        raise ValueError("at least one gain is required")
    if len(set(gains)) != len(gains):
        raise ValueError("gains must be unique")
    if any(not math.isfinite(gain) or not 0.0 <= gain <= 1.0 for gain in gains):
        raise ValueError("gains must be finite and in [0, 1]")

    checkpoint = torch.load(source, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, dict):
        raise TypeError("checkpoint must be a dictionary")
    model_config = checkpoint.get("model_config")
    if not isinstance(model_config, dict):
        raise TypeError("checkpoint model_config must be a dictionary")
    if int(model_config.get("play_hazard_adapter_size", 0)) <= 0:
        raise ValueError("checkpoint has no play-hazard adapter")
    source_gain = float(model_config.get("play_hazard_adapter_gain", 1.0))
    if source_gain != 1.0:
        raise ValueError("source checkpoint must have unit adapter gain")

    output_root.mkdir(parents=True, exist_ok=True)
    source_sha = _sha256(source)
    rows: list[dict[str, Any]] = []
    for gain in gains:
        calibrated = dict(checkpoint)
        calibrated_config = dict(model_config)
        calibrated_config["play_hazard_adapter_gain"] = gain
        calibrated["model_config"] = calibrated_config
        calibrated["posthoc_calibration"] = {
            "schema": "clasher.play_hazard_adapter_gain.v1",
            "source_checkpoint": str(source.resolve()),
            "source_sha256": source_sha,
            "gain": gain,
            "evaluation_only": True,
        }
        output = output_root / f"{source.stem}_{_gain_name(gain)}.pt"
        temporary = output.with_suffix(output.suffix + ".tmp")
        torch.save(calibrated, temporary)
        os.replace(temporary, output)
        rows.append(
            {
                "gain": gain,
                "checkpoint": str(output.resolve()),
                "sha256": _sha256(output),
            }
        )

    manifest = {
        "schema": "clasher.play_hazard_adapter_gain_sweep.v1",
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
    parser.add_argument("--gain", action="append", required=True, type=float)
    args = parser.parse_args()
    print(
        json.dumps(
            calibrate(
                source=args.source,
                output_root=args.output_root,
                gains=args.gain,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
