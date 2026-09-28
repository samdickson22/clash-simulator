"""Create an evaluation checkpoint with an explicit deterministic hierarchy."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import torch

from clasher.paths import resolve_path
from clasher.rl.model import PolicyConfig
from clasher.rl.oracle_corpus import file_sha256


def set_deterministic_hierarchy(
    *,
    source: Path,
    output: Path,
    hierarchy: str,
) -> dict[str, object]:
    if hierarchy not in {"slot", "play-gate"}:
        raise ValueError("hierarchy must be 'slot' or 'play-gate'")
    source = source.resolve()
    output = output.resolve()
    if source == output:
        raise ValueError("output checkpoint must differ from source")
    payload = torch.load(source, map_location="cpu", weights_only=False)
    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("source checkpoint is not a V2 recurrent policy")
    source_config = PolicyConfig.from_dict(payload["model_config"])
    target_config = replace(source_config, deterministic_hierarchy=hierarchy)
    updated = dict(payload)
    updated.pop("optimizer_state_dict", None)
    updated["model_config"] = target_config.to_dict()
    args = dict(payload.get("args") or {})
    args["deterministic_hierarchy"] = {
        "source_checkpoint": str(source),
        "source_hierarchy": source_config.deterministic_hierarchy,
        "target_hierarchy": hierarchy,
        "stochastic_distribution_changed": False,
    }
    updated["args"] = args
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(updated, output)
    return {
        "schema_version": 1,
        "source_checkpoint": str(source),
        "source_sha256": file_sha256(source),
        "output_checkpoint": str(output),
        "output_sha256": file_sha256(output),
        "source_hierarchy": source_config.deterministic_hierarchy,
        "target_hierarchy": hierarchy,
        "state_tensors_changed": 0,
        "optimizer_state_preserved": False,
        "stochastic_distribution_changed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--hierarchy", choices=("slot", "play-gate"), required=True)
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()
    result = set_deterministic_hierarchy(
        source=resolve_path(args.source, must_exist=True),
        output=resolve_path(args.output),
        hierarchy=args.hierarchy,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        report = resolve_path(args.json_out)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
