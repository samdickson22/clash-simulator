#!/usr/bin/env python3
"""TIERS Amendment 3 A3-P: all-cause Mac poll-lateness check from sealed session receipts only.

Outcome-blind and read-only. It reads a sealed `measure_tiers.py` Mac output directory, verifies the
receipt seal (receipt-manifest.json, its .sha256 sidecar and every listed file), then for every tier and
variant takes the opportunity poll rows of `decisions-tiers.jsonl` (default) and `gc-freeze.jsonl`
(freeze) and reports:
  - late_polls: opportunity polls with entered - scheduled > 25 ms, whether or not a GC event overlapped;
  - late_rate = late_polls / opportunities, and max_lateness_ms;
  - passes = late_rate <= 1% and max_lateness_ms <= 50 (the frozen gate-4 thresholds).

Combination with the frozen gate (declared before any Mac data exists): the frozen reducer evaluates gate 4
on v* = freeze if freeze_gc passes, else default (measure_tiers.py tiers-summary feasibility). A3-P is
applied to that same variant v*, so a tier is Mac-feasible only if the frozen feasibility holds AND
A3-P(v*) passes. A3-P can only remove feasibility. Both variants are also reported descriptively.
A tier with no opportunity polls in v* fails A3-P, as the frozen gc_summary does.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

TIERS = ("K0c", "S", "K2", "K4")
LATE_SECONDS, MAX_RATE, MAX_MS = .025, .01, 50.
SOURCES = {"default": "decisions-tiers.jsonl", "freeze": "gc-freeze.jsonl"}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_seal(directory, expected_manifest_sha):
    manifest = directory / "receipt-manifest.json"
    sidecar = (directory / "receipt-manifest.sha256").read_text().split()
    actual = sha(manifest)
    if sidecar != [actual, "receipt-manifest.json"] or actual != expected_manifest_sha:
        raise ValueError("Receipt seal mismatch")
    sealed = json.loads(manifest.read_text())
    for name, digest in sealed["files"].items():
        if sha(directory / name) != digest:
            raise ValueError("Sealed receipt file changed: " + name)
    present = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()}
    if present - set(sealed["files"]) - {"receipt-manifest.json", "receipt-manifest.sha256"}:
        raise ValueError("Unsealed file in receipt directory")
    return sealed


def check(rows):
    polls = [r for r in rows if r["opportunity"] is True]
    lateness = []
    for row in polls:
        value = row["entered"] - row["scheduled"]
        if not (math.isfinite(row["entered"]) and math.isfinite(row["scheduled"])):
            raise ValueError("Non-finite poll timestamps: " + row["poll_id"])
        lateness.append(value)
    if len({r["poll_id"] for r in polls}) != len(polls):
        raise ValueError("Duplicate poll rows")
    late = sum(value > LATE_SECONDS for value in lateness)
    rate = late / len(polls) if polls else None
    maximum = max(lateness, default=0.) * 1000
    return dict(opportunities=len(polls), late_polls=late, late_rate=rate,
                max_lateness_ms=maximum if polls else None,
                passes=rate is not None and rate <= MAX_RATE and maximum <= MAX_MS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipts", type=Path, required=True)
    ap.add_argument("--receipt-manifest-sha256", required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    directory = a.receipts.resolve()
    sealed = verify_seal(directory, a.receipt_manifest_sha256)
    # Only a completed session may yield feasibility: measure_tiers writes tiers-summary.json before its
    # final bundle/native validation and seals failures with status "failed".
    complete = json.loads((directory / "tiers-complete.json").read_text()) if "tiers-complete.json" in sealed["files"] else {}
    if (sealed.get("status") != "complete" or complete.get("completed") is not True
            or {"failure.json", "cleanup-failure.json"} & set(sealed["files"])):
        raise ValueError("A3-P requires a complete, sealed Mac session receipt")
    summary = json.loads((directory / "tiers-summary.json").read_text())
    if summary.get("dry_run") is not False:
        raise ValueError("A3-P applies to a Mac session receipt only")
    rows = {variant: [] for variant in SOURCES}
    for variant, name in SOURCES.items():
        path = directory / name
        if path.exists():
            for line in path.read_text().splitlines():
                row = json.loads(line)
                if row["variant"] != variant:
                    raise ValueError("Variant mismatch in " + name)
                rows[variant].append(row)
    result = {}
    for tier in TIERS:
        per = {v: check([r for r in rows[v] if r["tier"] == tier]) for v in SOURCES}
        chosen = "freeze" if summary["freeze_gc"][tier]["passes"] else "default"
        frozen = summary["feasibility"][tier]
        result[tier] = dict(variants=per, frozen_gate4_variant=chosen,
                            a3p_passes=per[chosen]["passes"],
                            frozen_feasible=frozen["feasible"],
                            feasible_after_a3p=frozen["feasible"] and per[chosen]["passes"],
                            reasons=frozen["reasons"] + ([] if per[chosen]["passes"] else ["A3-P all-cause poll lateness"]))
    record = dict(schema="clasher.mac-e4-session.a3p.v1", amendment="TIERS Amendment 3 A3-P",
                  receipts=str(directory), receipt_manifest_sha256=a.receipt_manifest_sha256,
                  thresholds=dict(late_seconds=LATE_SECONDS, max_rate=MAX_RATE, max_ms=MAX_MS),
                  combination="A3-P on the frozen gate-4 variant v*; can only remove feasibility; failure is not a technical failure and grants no repeat",
                  tiers=result, outcomes_read=False)
    with a.output.open("x") as stream:
        json.dump(record, stream, indent=1, sort_keys=True)
        stream.write("\n")
    print(json.dumps({t: r["feasible_after_a3p"] for t, r in result.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
