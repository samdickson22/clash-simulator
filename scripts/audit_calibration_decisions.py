"""Audit opened paired branches by declared physical family; never admit training."""

import argparse
import hashlib
import json
from pathlib import Path

from audit_reacting_public_branches import audit

from clasher.rl.calibration_decisions import (
    CandidatePair,
    DecisionCriteria,
    DecisionRoot,
    development_summary,
)
from clasher.rl.calibration_families import require_development_member


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_paired(path: Path):
    protocol = json.loads((path / "protocol.json").read_text())
    receipt = json.loads((path / "complete.json").read_text())
    if receipt.get("runtime_override", "missing") is not None:
        raise ValueError("production audit requires an explicit null runtime override")
    if receipt.get("sources_unchanged") is not True:
        raise ValueError("source stability receipt missing")
    if not protocol.get("family"):
        raise ValueError("explicit physical family assignment required")
    parents = receipt.get("parents", {})
    if len(parents) != 2:
        raise ValueError("both native and scalar parent receipts required")
    parent_results = []
    for parent, files in parents.items():
        if not {"results.json", "provenance.json", "complete.json"} <= files.keys():
            raise ValueError("incomplete parent digest receipt")
        for name, expected in files.items():
            if digest(Path(parent) / name) != expected:
                raise ValueError(f"parent digest changed: {parent}/{name}")
        parent_results.extend(json.loads((Path(parent) / "results.json").read_text()))
    results = json.loads((path / "results.json").read_text())
    canonical = lambda rows: sorted(json.dumps(r, sort_keys=True) for r in rows)
    if canonical(results) != canonical(parent_results):
        raise ValueError("paired results differ from verified parents")
    report = audit(path)
    roots = []
    # Response realizations remain grouped inside the same physical family.
    for seed in protocol["response_seeds"]:
        candidates = []
        for row in report["branches"]:
            if row["seed"] != seed:
                continue
            native, scalar = row["native_utility"], row["scalar_utility"]
            candidates.append(
                CandidatePair(
                    name=row["candidate"],
                    native_outcome=native[0],
                    native_hp_margin=float(native[1]),
                    scalar_outcome=scalar[0],
                    scalar_hp_margin=float(scalar[1]),
                )
            )
        roots.append(
            DecisionRoot(
                root_id=f"{protocol['root_duplicate_group_id']}:{protocol['root_tick']}:{protocol['owner']}:{seed}",
                family_id=protocol["family"],
                baseline="recorded",
                expected_candidates=tuple(c["name"] for c in protocol["candidates"]),
                candidates=tuple(candidates),
            )
        )
    return roots, {
        str(path.resolve() / name): digest(path / name)
        for name in ("protocol.json", "results.json", "complete.json")
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paired", type=Path, nargs="+", required=True)
    parser.add_argument("--criteria", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    draft = json.loads(args.criteria.read_text())
    criteria = DecisionCriteria.model_validate(draft["decision_criteria"])
    roots, sources = [], {}
    family_records = {}
    for path in args.paired:
        loaded, hashes = load_paired(path)
        protocol = json.loads((path / "protocol.json").read_text())
        family = require_development_member(
            args.registry, protocol["family"], protocol["root_duplicate_group_id"]
        )
        family_records[family.family_id] = family.model_dump()
        roots.extend(loaded)
        sources.update(hashes)
    report = development_summary(roots, criteria)
    report["sources"] = sources
    report["verified_family_records"] = family_records
    report["criteria_sha256"] = digest(args.criteria)
    report["auditor_sha256"] = digest(Path(__file__))
    report["family_assignment_scope"] = (
        "Declared development groups; no claim of random independent sampling."
    )
    with args.output.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "family_count",
                    "bad_families",
                    "clear_improvement_families",
                    "clear_regression_families",
                    "acceptance_passed",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
