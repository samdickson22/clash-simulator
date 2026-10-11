#!/usr/bin/env python3
"""TIERS Amendment 4, B.7: the hand-off receipt ``mac-sets-selection.json``.

Before sealing, every artifact is re-hashed and every stage receipt is checked
against the one before it (selection -> assembly -> conversion -> student
reference -> cross-check / memory). The receipt binds, by SHA, capture verification,
pool and invalid counts, game order and truncation, fill quotas, all ids (in
mac-sets.json), the schedule, the fixture and its fingerprint, the conversion, the
student reference and its cross-check, the memory check and the script bytes. T1
merges ``mac-sets.json`` (sets + packet_schedule) and ``student-reference.json`` into
its reviewed registration packet and seals it; this receipt carries no outcome data.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import macreg_io as io
import selection

SCRIPTS = ("selection.py", "macreg_io.py", "build_sets.py", "assemble_states.py", "student_reference.py",
           "memory_check.py", "seal_receipt.py", "stage_nocopy.py", "fetch_captures.sh", "verify_captures.py",
           "build_runtime.sh", "run_phase3.sh")


def verified(a):
    """Re-hash every artifact and check the receipt chain; returns the loaded pieces (fail closed)."""
    from convert_states import fingerprint
    from student_reference import load_reference, selection_sets
    stage_sha, stage, sets = selection_sets(a.selection)
    io.verify_artifacts({a.selection / "pool.json": stage["output_sha256"]["pool"]})
    registration = io.read_pinned_json(a.selection / "mac-sets.json", stage["output_sha256"]["sets"])
    plan = io.read_pinned_json(a.selection / "fixture-plan.json", stage["output_sha256"]["plan"])
    assembly_sha = io.file_sha(a.assembly / "assembly.json")
    assembly = json.loads((a.assembly / "assembly.json").read_text())
    digests = io.read_pinned_json(a.assembly / "fixture-digests.json", assembly["fixture_digests_sha256"])
    conversion_sha = io.file_sha(a.state_rows / "conversion-receipt.json")
    conversion = json.loads((a.state_rows / "conversion-receipt.json").read_text())
    reference_sha, reference, refs = load_reference(a.reference, sets, stage_sha)
    cross_sha = io.file_sha(a.reference / "student-cross-check.json")
    cross = json.loads((a.reference / "student-cross-check.json").read_text())
    memory_sha = io.file_sha(a.memory / "mac-profile-memory.json")
    memory = json.loads((a.memory / "mac-profile-memory.json").read_text())
    fixture = assembly["expected_fingerprint"]
    io.verify_artifacts({a.assembly / "states.pkl": assembly["states"]["sha256"],
                         a.state_rows / "states-rows.json": conversion["output"]["index"]["sha256"],
                         a.state_rows / "states-rows.bin": conversion["output"]["container"]["sha256"]})
    checks = dict(
        assembly_from_selection=assembly["selection_stage_sha256"] == stage_sha and assembly["inputs"]["fixture_plan"] == stage["output_sha256"]["plan"],
        fixture_digests=[e["id"] for e in digests["rows"]] == plan["fixture_ids"] and fingerprint(digests["rows"]) == fixture
        and digests["fixture_canonical_fingerprint"] == fixture and fingerprint(digests["rows"][:io.END_ROWS]) == io.END_FINGERPRINT
        and assembly["end_prefix"]["equal"] is True,
        conversion_pass=conversion["status"] == "PASS" and conversion["verification"]["source_verified"] is True
        and conversion["fixture_canonical_fingerprint"] == fixture and conversion["assembled"]["sha256"] == assembly["states"]["sha256"]
        and conversion["rows"] == len(plan["fixture_ids"]),
        reference_chain=reference["assembly_sha256"] == assembly_sha and reference["conversion_receipt_sha256"] == conversion_sha
        and reference["fixture_canonical_fingerprint"] == fixture and reference["states"] == len(sets["agreement"]) == len(refs),
        cross_check_pass=cross["passes"] is True and cross["states"] == 300 and cross["student_reference_receipt_sha256"] == reference_sha
        and cross["student_reference_sha256"] == reference["student_reference"]["sha256"] and cross["selection_stage_sha256"] == stage_sha,
        memory_pass=memory["passes"] is True and memory["student_reference_receipt_sha256"] == reference_sha
        and memory["bundle_manifest_sha256"] == reference["bundle_manifest_sha256"] and memory["sets_sha256"] == stage["sets_sha256"]
        and memory["agreement"] == len(sets["agreement"]) and memory["forwards_per_child"] == 2001
        and memory["states_sha256"] == assembly["states"]["sha256"] and memory["conservative_sum_vmhwm_bytes"] <= memory["cap_bytes"],
        counts=len(sets["golden"]) == 125 and all(len(sets["speed"][t]) == 300 for t in io.TIERS)
        and len(sets["agreement"]) >= selection.AGREEMENT and len(sets["packets"]) == selection.PACKETS,
        schedule_ids_equal_packets=[e["id"] for e in registration["packet_schedule"]] == sets["packets"],
    )
    selection.check_schedule(registration["packet_schedule"], {e["id"]: e["tick"] for e in registration["packet_schedule"]})
    if not all(checks.values()):
        raise SystemExit("Hand-off checks failed: " + repr([k for k, v in checks.items() if not v]))
    receipts = {"selection-stage.json": stage_sha, "assembly.json": assembly_sha, "conversion-receipt.json": conversion_sha,
                "student-reference-receipt.json": reference_sha, "student-cross-check.json": cross_sha,
                "mac-profile-memory.json": memory_sha}
    return stage, registration, assembly, conversion, reference, cross, memory, checks, receipts


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime-root", type=Path, required=True)
    p.add_argument("--e4v3", type=Path)
    for name in ("--selection", "--assembly", "--state-rows", "--reference", "--memory", "--output"):
        p.add_argument(name, type=Path, required=True)
    a = p.parse_args(argv)
    io.add_e4v3(a.e4v3 or Path(a.runtime_root) / io.E4V3_REL)
    stage, registration, assembly, conversion, reference, cross, memory, checks, receipts = verified(a)
    schedule = registration["packet_schedule"]
    canonical_schedule = json.dumps(schedule, sort_keys=True, separators=(",", ":"), allow_nan=False)
    receipt = dict(
        schema="clasher.tiers-a4.mac-sets-selection.v1", utc=io.utc(), amendment="TIERS Amendment 4 (Mac registration inputs)",
        captures=stage["captures"], capture_receipt=stage["capture_receipt"], lineage=stage["lineage"],
        validity={k: stage["validity"][k] for k in ("rows", "invalid", "invalid_fraction", "invalid_ids", "by_tier")},
        packet_games=stage["packet_games"], agreement=stage["agreement"], counts=stage["counts"],
        schedule=dict(stage["schedule"], canonical_sha256=hashlib.sha256(canonical_schedule.encode()).hexdigest()),
        sets_sha256=stage["sets_sha256"], mac_sets_sha256=stage["output_sha256"]["sets"],
        fixture_plan_sha256=stage["output_sha256"]["plan"], pool_metadata_sha256=stage["output_sha256"]["pool"],
        fixture=dict(rows=assembly["rows"], extra_rows=assembly["extra_rows"], end_prefix=assembly["end_prefix"],
                     states_sha256=assembly["states"]["sha256"], states_bytes=assembly["states"]["bytes"],
                     fixture_digests_sha256=assembly["fixture_digests_sha256"],
                     fixture_canonical_fingerprint=assembly["expected_fingerprint"]),
        conversion=dict(index=conversion["output"]["index"], container=conversion["output"]["container"],
                        converter_sha256=conversion["converter_sha256"], verification=conversion["verification"]),
        student_reference=dict(sha256=reference["student_reference"]["sha256"], states=reference["states"],
                               host=reference["host"], versions=reference["versions"], runtime=reference["runtime"],
                               cross_check={k: cross[k] for k in ("passes", "states", "bit_exact", "max_abs_gate", "max_abs_logit", "tolerance", "end_speed_reference")}),
        memory={k: memory[k] for k in ("conservative_sum_vmhwm_bytes", "sampled_concurrent_vmrss_peak_bytes", "cap_bytes", "passes", "caveat",
                                       "agreement", "forwards_per_child", "bundle_manifest_sha256")},
        receipts_sha256=receipts, script_sha256={n: io.file_sha(io.HERE / n) for n in SCRIPTS},
        e4v3_pins=stage["e4v3_pins"], runtime=stage["runtime"], checks=checks,
        outcomes_read=False, games_read=False, timing=False)
    a.output.mkdir(parents=True, exist_ok=True)
    print(json.dumps(dict(sha256=io.write_json(a.output / "mac-sets-selection.json", receipt),
                          fingerprint=assembly["expected_fingerprint"])))


if __name__ == "__main__":
    main()
