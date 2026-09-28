from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

import torch

from clasher.rl.model import PolicyConfig


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def set_equivariant_timing_pool(
    payload: dict[str, Any],
    *,
    timing_pool: str,
) -> dict[str, Any]:
    config = PolicyConfig.from_dict(payload["model_config"])
    if not config.equivariant_slot_choice:
        raise ValueError("timing-pool upgrade requires equivariant slot choice")
    if timing_pool not in {"log-mass", "max"}:
        raise ValueError("timing pool must be 'log-mass' or 'max'")
    upgraded = PolicyConfig.from_dict(
        {
            **config.to_dict(),
            "equivariant_deterministic_timing_pool": timing_pool,
        }
    )
    result = dict(payload)
    result["model_config"] = upgraded.to_dict()
    result.pop("optimizer_state_dict", None)
    result["equivariant_timing_pool_upgrade"] = {
        "schema_version": 1,
        "timing_pool": timing_pool,
        "stochastic_play_mass_unchanged": True,
        "model_tensors_unchanged": True,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timing-pool", choices=("log-mass", "max"), default="max")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = torch.load(args.input, map_location="cpu", weights_only=False)
    result = set_equivariant_timing_pool(payload, timing_pool=args.timing_pool)
    result["equivariant_timing_pool_upgrade"] = {
        **result["equivariant_timing_pool_upgrade"],
        "source_checkpoint": str(args.input.resolve()),
        "source_checkpoint_sha256": _sha256(args.input),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(result, args.output)
    print(f"output={args.output.resolve()}")
    print(f"sha256={_sha256(args.output)}")


if __name__ == "__main__":
    main()
