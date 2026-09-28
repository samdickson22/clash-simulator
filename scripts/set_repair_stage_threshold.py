from __future__ import annotations

import argparse
import hashlib
from dataclasses import replace
from pathlib import Path

import torch

from clasher.paths import resolve_path
from clasher.rl.model import PolicyConfig


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def set_stage_threshold(
    *,
    checkpoint_path: Path,
    output_path: Path,
    stage_index: int,
    threshold: float,
) -> None:
    if not 0.0 <= threshold < 1.0:
        raise ValueError("prototype threshold must be in [0, 1)")
    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    config = PolicyConfig.from_dict(payload["model_config"])
    if not 0 <= stage_index < len(config.repair_stage_sizes):
        raise ValueError("repair stage index is out of range")
    counts = config.repair_stage_prototype_counts + (0,) * (
        len(config.repair_stage_sizes)
        - len(config.repair_stage_prototype_counts)
    )
    if counts[stage_index] == 0:
        raise ValueError("selected repair stage has no prototypes")
    thresholds = list(
        config.repair_stage_prototype_thresholds
        + (config.repair_stage_prototype_threshold,)
        * (
            len(config.repair_stage_sizes)
            - len(config.repair_stage_prototype_thresholds)
        )
    )
    source_threshold = thresholds[stage_index]
    thresholds[stage_index] = threshold
    updated = replace(
        config,
        repair_stage_prototype_thresholds=tuple(thresholds),
    )
    payload.pop("optimizer_state", None)
    payload.pop("optimizer_state_dict", None)
    payload["model_config"] = updated.to_dict()
    payload["repair_stage_threshold_sweep"] = {
        "source_checkpoint": str(checkpoint_path),
        "source_sha256": _sha256(checkpoint_path),
        "stage_index": stage_index,
        "source_threshold": source_threshold,
        "threshold": threshold,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    torch.save(payload, temporary_path)
    temporary_path.replace(output_path)
    print(f"saved={output_path}")
    print(f"sha256={_sha256(output_path)}")
    print(f"stage={stage_index} threshold={source_threshold}->{threshold}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a checkpoint-only repair-stage threshold sweep variant."
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage-index", type=int, required=True)
    parser.add_argument("--threshold", type=float, required=True)
    args = parser.parse_args()
    set_stage_threshold(
        checkpoint_path=resolve_path(args.checkpoint, must_exist=True),
        output_path=resolve_path(args.output),
        stage_index=args.stage_index,
        threshold=args.threshold,
    )


if __name__ == "__main__":
    main()
