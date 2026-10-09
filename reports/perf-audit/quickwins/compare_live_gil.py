"""Compare two full-budget corrected live replay receipts exactly."""
import argparse
import hashlib
import json
from pathlib import Path


def compare(baseline, variant):
    for field in ("input_sha256", "reference_sha256", "qualifier_sha256", "driver_sha256",
                  "pythonhashseed", "config_sha256", "templates_sha256", "flags", "live_sources"):
        assert baseline[field] == variant[field], field
    def rows(receipt):
        return {(r["repeat"], r["match"], r["sequence"], r["parallel"]): r
                for r in receipt["samples"]}
    a, b = rows(baseline), rows(variant)
    assert a.keys() == b.keys()
    for key in a:
        for field in ("candidates", "root_digests", "scores", "scores_sha256", "action"):
            assert a[key][field] == b[key][field], (key, field)
    records = [{"key": key, **{field: a[key][field] for field in
               ("candidates", "root_digests", "scores", "action")}} for key in sorted(a)]
    return dict(schema="clasher.native-gil.live-comparison.v1", mismatches=0,
                paired_samples=len(records),
                decisions=baseline["exactness"]["unique_decisions"],
                candidate_root_scores=baseline["exactness"]["candidate_root_scores"],
                results_sha256=hashlib.sha256(json.dumps(records, separators=(",", ":")).encode()).hexdigest(),
                baseline_binary_sha256=baseline["native_sha256"],
                variant_binary_sha256=variant["native_sha256"],
                baseline_decision_ms=baseline["decision_ms"],
                variant_decision_ms=variant["decision_ms"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("variant", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    assert not args.output.exists(), "new output path required"
    result = compare(json.loads(args.baseline.read_text()), json.loads(args.variant.read_text()))
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))
