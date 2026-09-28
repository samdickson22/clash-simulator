"""Check exact weight equality on the full existing corpus without fitting a model."""

import json
import time
from pathlib import Path

import numpy as np
from fast_weights import fitting_weights
from scalar_evaluation import fitting_weights as reference_weights
from terminal_labels import sha


def main():
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_grouped_weight_parity_20260913.json"
    if output.exists():
        raise ValueError("preserve existing weight parity audit")
    manifest_path = root / "reports/hog26_scaling_globals_comparison_20260912/fitting_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    progress, lengths, families = [], [], []
    for record in manifest["input_games"]:
        if sha(record["path"]) != record["sha256"]:
            raise ValueError("weight probe archive changed")
        with np.load(record["path"], allow_pickle=False) as archive:
            p = archive["global_features"][:, 0]
            metadata = json.loads(str(archive["metadata_json"]))
        progress.append(p)
        lengths.append(len(p))
        families.append(int(metadata["family_id"][-3:]) // 2)
    ids = np.repeat(np.arange(len(lengths)), lengths)
    progress = np.concatenate(progress)
    folds = np.repeat(families, lengths)
    results = []
    for fold in range(4):
        selected = folds != fold
        began = time.monotonic()
        expected = reference_weights(ids, progress, selected)
        original_seconds = time.monotonic() - began
        began = time.monotonic()
        actual = fitting_weights(ids, progress, selected)
        grouped_seconds = time.monotonic() - began
        if any(not np.array_equal(a, b) for a, b in zip(actual, expected, strict=True)):
            raise ValueError("grouped weights differ from the original exact formula")
        results.append({"fold": fold, "rows": len(ids), "exact": True,
                        "original_seconds": original_seconds, "grouped_seconds": grouped_seconds})
        print(json.dumps(results[-1]), flush=True)
    with output.open("x") as stream:
        json.dump({"status": "exact-existing-corpus-weight-parity", "games": len(lengths), "rows": len(ids),
                   "folds": results, "manifest_sha256": sha(manifest_path),
                   "sources": {str(p): sha(p) for p in (Path(__file__), Path(__file__).with_name("fast_weights.py"),
                                                         root / "experiments/hog26_scalar_pilot/scalar_evaluation.py")},
                   "fitting": False, "acceptance": False,
                   "scope": "Same WDL and margin loss weights on existing1536-game data; no objective change or model update."}, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
