"""Diagnostic early parity check; never replaces the required completed-corpus gate."""

import argparse
import json
from pathlib import Path

from parallel_engine import compare_arrays
from probe_worker import sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("preserve existing live parity diagnostic")
    root = Path(__file__).resolve().parents[2]
    prefix_path = root / "reports/hog26_training_expansion_sequential_retired_prefix_20260913.json"
    prefix = json.loads(prefix_path.read_text())
    directory = root / "datasets/derived/hog26_training_expansion_parallel_seed1280101_20260913"
    checked = []
    for item in prefix["input_games"]:
        original = Path(item["path"])
        parallel = directory / original.name
        audit_path = parallel.with_suffix(".audit.json")
        if not audit_path.is_file():
            continue
        audit = json.loads(audit_path.read_text())
        if sha(original) != item["sha256"] or sha(parallel) != audit["sha256"]:
            raise ValueError("live parity archive authority differs")
        fields = compare_arrays(original, parallel)
        checked.append({"path": original.name, "parallel_sha256": audit["sha256"],
                        "sequential_sha256": item["sha256"], "fields": len(fields), "exact": True})
    if not checked:
        raise ValueError("no completed matching games to compare")
    with args.output.open("x") as stream:
        json.dump({"status": "partial-prefix-parity-diagnostic", "checked_games": len(checked),
                   "retired_prefix_games": prefix["games"], "all_checked_arrays_exact": True,
                   "comparisons": checked, "prefix_manifest_sha256": sha(prefix_path),
                   "parallel_plan_sha256": sha(root / "reports/hog26_training_expansion_parallel_frozen_plan_20260913.json"),
                   "source_sha256": sha(__file__), "fitting_allowed": False, "acceptance": False,
                   "scope": "Early diagnostic only. Full collection, formal prefix parity and combined audit are still required."}, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": "partial-prefix-parity-diagnostic", "checked_games": len(checked), "exact": True}), flush=True)


if __name__ == "__main__":
    main()
