"""Build one deterministic mechanics-slot probe from independent training seeds."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import os
import tempfile
from pathlib import Path
from typing import Any

import torch

from clasher.paths import resolve_path
from clasher.rl.oracle_corpus import file_sha256


def _load_probe(path: Path) -> dict[str, Any]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict):
        raise TypeError(f"probe checkpoint is not a mapping: {path}")
    required = {"semantics_version", "hidden_size", "state_dict", "token_names"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"probe checkpoint lacks required fields {missing}: {path}")
    if not isinstance(payload["state_dict"], dict) or not payload["state_dict"]:
        raise ValueError(f"probe checkpoint has no model state: {path}")
    return payload


def average_probes(*, sources: list[Path], output: Path) -> dict[str, Any]:
    resolved = sorted({path.resolve() for path in sources}, key=str)
    if len(resolved) < 2:
        raise ValueError("at least two unique probe checkpoints are required")
    missing = [str(path) for path in resolved if not path.is_file()]
    if missing:
        raise FileNotFoundError("probe checkpoints do not exist: " + ", ".join(missing))
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite probe ensemble: {output}")

    probes = [_load_probe(path) for path in resolved]
    architecture = {
        (
            int(probe["semantics_version"]),
            int(probe["hidden_size"]),
            tuple(str(token) for token in probe["token_names"]),
        )
        for probe in probes
    }
    if len(architecture) != 1:
        raise ValueError("probe checkpoints are not architecture/vocabulary compatible")
    semantics_version, hidden_size, token_names = architecture.pop()

    state_keys = [set(probe["state_dict"]) for probe in probes]
    if any(keys != state_keys[0] for keys in state_keys[1:]):
        raise ValueError("probe checkpoints do not contain the same state tensors")
    state_dict: dict[str, torch.Tensor] = {}
    for key in sorted(state_keys[0]):
        tensors = [probe["state_dict"][key] for probe in probes]
        if any(not isinstance(tensor, torch.Tensor) for tensor in tensors):
            raise TypeError(f"probe state is not a tensor: {key}")
        reference = tensors[0]
        if not reference.is_floating_point():
            raise TypeError(f"probe state must be floating point: {key}")
        if any(
            tensor.shape != reference.shape or tensor.dtype != reference.dtype
            for tensor in tensors[1:]
        ):
            raise ValueError(f"probe state shape/dtype differs: {key}")
        if any(not bool(torch.isfinite(tensor).all()) for tensor in tensors):
            raise ValueError(f"probe state contains non-finite values: {key}")
        state_dict[key] = torch.stack(tensors, dim=0).mean(dim=0)

    payload: dict[str, Any] = {
        "schema_version": 1,
        "semantics_version": semantics_version,
        "hidden_size": hidden_size,
        "state_dict": state_dict,
        "token_names": token_names,
        "ensemble": {
            "schema": "equal-weight-mechanics-slot-probe-ensemble-v1",
            "reduction": "arithmetic-parameter-mean",
            "sources": [
                {"path": str(path), "sha256": file_sha256(path)} for path in resolved
            ],
            "weights": [1.0 / len(resolved)] * len(resolved),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary)
    try:
        torch.save(payload, temporary_path)
        os.replace(temporary_path, output)
    finally:
        temporary_path.unlink(missing_ok=True)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-checkpoint", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = average_probes(
        sources=[resolve_path(path, must_exist=True) for path in args.probe_checkpoint],
        output=resolve_path(args.output),
    )
    print(
        {
            "output": str(resolve_path(args.output, must_exist=True)),
            "sources": len(payload["ensemble"]["sources"]),
            "semantics_version": payload["semantics_version"],
            "hidden_size": payload["hidden_size"],
        }
    )


if __name__ == "__main__":
    main()
