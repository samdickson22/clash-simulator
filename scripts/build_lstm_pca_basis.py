from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze a PCA intervention basis from captured LSTM hidden states"
    )
    parser.add_argument("--activations", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--components", type=int, default=3)
    args = parser.parse_args()
    if args.components <= 0:
        raise ValueError("components must be positive")

    source_path = Path(args.activations).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with np.load(source_path) as payload:
        hidden = np.asarray(payload["hidden"], dtype=np.float64)
    if hidden.ndim != 2 or hidden.shape[0] < 2:
        raise ValueError("hidden activations must be a nontrivial [samples, units] array")
    if args.components > min(hidden.shape):
        raise ValueError("requested more components than the activation matrix supports")

    mean = hidden.mean(axis=0)
    centered = hidden - mean
    _left, singular_values, right = np.linalg.svd(centered, full_matrices=False)
    variance = np.square(singular_values)
    explained = variance / variance.sum()
    components = right[: args.components]
    np.savez(
        output_path,
        hidden_mean=mean.astype(np.float32),
        hidden_components=components.astype(np.float32),
        explained_variance_ratio=explained[: args.components].astype(np.float64),
    )
    manifest_path = output_path.with_suffix(".json")
    manifest = {
        "schema_version": 1,
        "source_activations": str(source_path),
        "source_activations_sha256": _sha256(source_path),
        "source_samples": int(hidden.shape[0]),
        "hidden_units": int(hidden.shape[1]),
        "components": args.components,
        "explained_variance_ratio": [
            float(value) for value in explained[: args.components]
        ],
        "cumulative_explained_variance": float(explained[: args.components].sum()),
        "intervention": (
            "after each LSTMCell step, replace h with "
            "h - ((h - mean) @ components.T) @ components; carry patched h forward; "
            "leave cell state unchanged"
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    manifest["basis_sha256"] = _sha256(output_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"basis={output_path}")
    print(f"basis_sha256={manifest['basis_sha256']}")
    print(f"manifest={manifest_path}")
    print(
        f"cumulative_explained_variance={manifest['cumulative_explained_variance']:.9f}"
    )


if __name__ == "__main__":
    main()
