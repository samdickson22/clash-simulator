"""Replay one excluded preflight case in a fresh process and compare every array."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from parallel_engine import compare_arrays, initialize, play


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    began = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--case", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    if (plan["schema"] != "clasher.parallel-preflight-replay.v1" or plan["fitting"] is not False
            or not 0 <= args.case < len(plan["cases"])):
        raise ValueError("invalid excluded parallel replay contract")
    case = plan["cases"][args.case]
    if sha(case["reference_path"]) != case["reference_sha256"]:
        raise ValueError("sequential preflight reference changed")
    path = args.output / case["name"]
    if path.exists():
        raise ValueError("preserve existing replay output")
    root = Path(__file__).resolve().parents[2]
    engine = initialize(root, plan["source_authority"]["contract"]["canonical_names"])
    audit = play(engine, plan=plan, case=case, path=path, mode="preflight")
    fields = compare_arrays(case["reference_path"], path)
    with (args.output / f"receipt-{args.case:03d}.json").open("x") as stream:
        json.dump({"case": args.case, "path": path.name, "sha256": sha(path),
                   "reference_sha256": case["reference_sha256"], "arrays_exact": True,
                   "compared_fields": fields, "rows": audit["rows"], "seconds_from_main": time.monotonic() - began,
                   "scope": "Excluded replay; only provenance metadata differs from sequential preflight."}, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
