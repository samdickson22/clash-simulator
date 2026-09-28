"""Create a weight-identical checkpoint with a different model-owned clock rate."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"

import argparse
import json
from dataclasses import replace
from pathlib import Path

import torch

from clasher.paths import resolve_path
from clasher.rl.model import PolicyConfig
from clasher.rl.oracle_corpus import file_sha256


def set_structured_clock_horizon(
    *, source: Path, output: Path, horizon_steps: int
) -> dict[str, object]:
    if horizon_steps <= 0:
        raise ValueError("clock horizon steps must be positive")
    source = source.resolve()
    output = output.resolve()
    if source == output:
        raise ValueError("output checkpoint must differ from source")
    payload = torch.load(source, map_location="cpu", weights_only=False)
    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("source checkpoint is not a V2 recurrent policy")
    source_config = PolicyConfig.from_dict(payload["model_config"])
    if source_config.memory_kind != "structured":
        raise ValueError("clock horizon conversion requires structured memory")
    target_config = replace(
        source_config, structured_clock_horizon_steps=horizon_steps
    )
    updated = dict(payload)
    updated.pop("optimizer_state_dict", None)
    updated["model_config"] = target_config.to_dict()
    updated["structured_clock_horizon_conversion"] = {
        "schema_version": 1,
        "source_checkpoint": str(source),
        "source_sha256": file_sha256(source),
        "source_horizon_steps": source_config.structured_clock_horizon_steps,
        "target_horizon_steps": horizon_steps,
        "state_tensors_changed": 0,
        "optimizer_state_preserved": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(updated, output)
    return {
        **updated["structured_clock_horizon_conversion"],
        "output_checkpoint": str(output),
        "output_sha256": file_sha256(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--horizon-steps", type=int, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = set_structured_clock_horizon(
        source=resolve_path(args.source, must_exist=True),
        output=resolve_path(args.output),
        horizon_steps=args.horizon_steps,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out is not None:
        report = resolve_path(args.json_out)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
