#!/usr/bin/env python3
"""Mechanical candidate-repeat classification; no human override or activation."""
import argparse
import json
from pathlib import Path
import re
from receipts import ReceiptStore, sha, verify_files


def classify(directory, fleet_reference=False):
    directory = Path(directory)
    manifest = json.loads((directory / "receipt-manifest.json").read_text())
    verify_files(directory, manifest["files"])
    if fleet_reference:
        from fleet_validity import classify_attempt
        return dict(**classify_attempt(directory,manifest),
            authority="classification only; at most one separately authorized technical repeat",
            source_manifest_sha256=sha(directory/"receipt-manifest.json"))
    failure = json.loads((directory / "failure.json").read_text()) if (directory / "failure.json").exists() else {}
    error = failure.get("error", "")
    reasons = []
    # Exactness, feasibility and agreement failures never grant a repeat.
    gate_failure = any(word in error for word in ("Exactness mismatch", "Zero-budget", "Zero native budget"))
    if error and not gate_failure:
        if "Pin mismatch:" in error or "manifest SHA mismatch" in error:
            reasons.append("staging pin mismatch")
        elif "Traceback (most recent call last)" in error and "quiescence census failed" not in error:
            reasons.append("harness/load exception")
    path = directory / "capacity.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    if any(p["foreign_over_one_core_seconds"] > 60 for r in rows for p in r["processes"]):
        reasons.append("foreign process above one core for over 60 seconds")
    boot = {r["boottime"]["stdout"] for r in rows if "boottime" in r}
    if len(boot) > 1 or any(abs(r.get("wall_monotonic_offset_change_seconds", 0)) > 3 for r in rows):
        reasons.append("host sleep/reboot clock evidence")
    # Thermal failure must be present BEFORE thermal warmup starts.
    pre = [r for r in rows if r["phase"] in ("pre-session-census", "D0", "D1", "D2", "D3")]
    if any(any(int(x) < 100 for x in re.findall(r"CPU_Speed_Limit\s*[=:]\s*(\d+)",
        r.get("thermal", {}).get("stdout", ""))) for r in pre):
        reasons.append("pre-D4 CPU speed limit below 100 percent")
    return dict(technical_repeat_candidate=bool(reasons) and not gate_failure,
                reasons=reasons, exactness_failure=gate_failure, final=False,
                authority="classification only; a repeat still needs separate session authorization",
                source_manifest_sha256=sha(directory / "receipt-manifest.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fleet-reference",action="store_true")
    args = parser.parse_args()
    store = ReceiptStore(args.output, "MECHANICAL-FAILURE-CLASSIFICATION")
    store.write("classification.json", classify(args.receipts,args.fleet_reference))
    store.seal("complete")


if __name__ == "__main__":
    main()
