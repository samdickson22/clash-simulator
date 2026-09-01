from __future__ import annotations

import hashlib
import json
import os
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np


class RolloutLike(Protocol):
    @property
    def transitions(self) -> int: ...


def _array_record(value: np.ndarray) -> dict[str, Any]:
    contiguous = np.ascontiguousarray(value)
    return {
        "kind": "ndarray",
        "dtype": contiguous.dtype.str,
        "shape": list(contiguous.shape),
        "sha256": hashlib.sha256(
            contiguous.tobytes(order="C")
        ).hexdigest(),
    }


def build_rollout_audit(
    rollout: RolloutLike,
    *,
    update: int,
    seed: int,
) -> dict[str, Any]:
    """Build an exact, pickle-free digest of one pre-optimization rollout."""

    if not is_dataclass(rollout) or isinstance(rollout, type):
        raise TypeError("rollout audit requires a dataclass instance")
    if update <= 0:
        raise ValueError("rollout update must be positive")

    records: dict[str, Any] = {}
    for field in fields(rollout):
        value = getattr(rollout, field.name)
        if isinstance(value, np.ndarray):
            records[field.name] = _array_record(value)
        elif value is None:
            records[field.name] = {"kind": "none"}
        elif isinstance(value, (bool, int, float, str)):
            records[field.name] = {"kind": "scalar", "value": value}
        else:
            raise TypeError(
                f"unsupported rollout audit field {field.name}: {type(value).__name__}"
            )

    canonical_records = json.dumps(
        records,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return {
        "schema": "clasher.pre-optimization-rollout-audit.v1",
        "update": update,
        "seed": seed,
        "transitions": int(rollout.transitions),
        "rollout_sha256": hashlib.sha256(canonical_records).hexdigest(),
        "fields": records,
    }


def write_rollout_audit(
    path: Path,
    rollout: RolloutLike,
    *,
    update: int,
    seed: int,
) -> dict[str, Any]:
    """Publish one audit atomically and refuse to replace prior evidence."""

    if path.exists():
        raise FileExistsError(f"refusing to overwrite rollout audit: {path}")
    payload = build_rollout_audit(rollout, update=update, seed=seed)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(encoded, encoding="utf-8")
        if path.exists():
            raise FileExistsError(f"refusing to overwrite rollout audit: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return payload
