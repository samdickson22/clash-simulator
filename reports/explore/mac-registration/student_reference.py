#!/usr/bin/env python3
"""TIERS Amendment 4, B.6: fleet-CPU student logits for every agreement state.

``compute``: on 05 (3990X, x86-64 Linux, END-A3-equal runtime, 1 Torch thread,
nice 19, one core, no timing), verify the selection -> assembly -> conversion
chain against the current bytes, build an offline Mac-profile bundle from the
converted fixture and write ``student-reference.json`` = {id: TierBackend.infer(id,
"cpu")} exactly as prepare_bundle's dry run wrote it (receipts.canonical; rank keys
become strings). The runtime is bootstrapped once, by TierBackend itself.

``cross-check``: on the 300 S speed ids, every record must equal T1's pooled END
fleet S forward (speed-reference.json [S][id].forward): same legal set, the same
discrete gate and ordered top-8 (receipts.agreement ``equal``), and gate and every
legal logit within the F1 tolerance 1e-4. Otherwise the reference is recomputed
on 01 after its END pool. Only S speed states have pooled student forwards, so this
gate samples the platform; it cannot certify every agreement state (disclosed).
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import macreg_io as io

TOLERANCE = 1e-4  # F1 near-tie tolerance (receipts.agreement)


def cross_check(refs, end_speed, ids, threshold, agreement):
    """Pure comparison; refs and END forwards are JSON-shaped (string rank keys)."""
    records, failures = [], []
    for identity in ids:
        forward = end_speed["S"][identity]["forward"]
        if forward is None:
            raise ValueError("Missing pooled END S forward: " + identity)
        old = dict(forward, ranks={int(k): v for k, v in forward["ranks"].items()})
        new = dict(refs[identity], ranks={int(k): v for k, v in refs[identity]["ranks"].items()})
        if old["legal"] != new["legal"] or set(old["ranks"]) != set(old["legal"]) or set(new["ranks"]) != set(new["legal"]):
            failures.append(identity)
            records.append(dict(id=identity, legal_equal=False))
            continue
        check = agreement(old, new, threshold)
        gate = abs(old["gate"] - new["gate"])
        rank = max((abs(old["ranks"][a] - new["ranks"][a]) for a in old["legal"]), default=0.)
        exact = old["gate"] == new["gate"] and all(old["ranks"][a] == new["ranks"][a] for a in old["legal"])
        ok = check["equal"] and gate <= TOLERANCE and rank <= TOLERANCE
        if not ok:
            failures.append(identity)
        records.append(dict(id=identity, legal_equal=True, gate_and_top8_equal=check["equal"],
                            max_abs_gate=gate, max_abs_logit=rank, bit_exact=exact, passes=ok))
    return dict(passes=not failures and len(records) == len(ids) == 300, states=len(records), failures=failures,
                bit_exact=sum(r.get("bit_exact", False) for r in records),
                max_abs_gate=max((r.get("max_abs_gate", 0.) for r in records), default=0.),
                max_abs_logit=max((r.get("max_abs_logit", 0.) for r in records), default=0.),
                tolerance=TOLERANCE, records=records)


def selection_sets(selection):
    """The reviewed sets, bound to the selection-stage receipt (current bytes)."""
    stage_sha = io.file_sha(selection / "selection-stage.json")
    stage = json.loads((selection / "selection-stage.json").read_text())
    sets = io.read_pinned_json(selection / "mac-sets.json", stage["output_sha256"]["sets"])["sets"]
    if io.sets_sha256(sets) != stage["sets_sha256"]:
        raise ValueError("mac-sets.json differs from its stage receipt")
    return stage_sha, stage, sets


def verified_chain(a):
    """selection -> assembly -> conversion, each receipt bound to the previous and to the current bytes."""
    stage_sha, stage, sets = selection_sets(a.selection)
    assembly_sha = io.file_sha(a.assembly / "assembly.json")
    assembly = json.loads((a.assembly / "assembly.json").read_text())
    conversion_sha = io.file_sha(a.state_rows / "conversion-receipt.json")
    conversion = json.loads((a.state_rows / "conversion-receipt.json").read_text())
    if assembly["selection_stage_sha256"] != stage_sha or assembly["inputs"]["fixture_plan"] != stage["output_sha256"]["plan"]:
        raise ValueError("Assembly was not built from this selection")
    if conversion["status"] != "PASS" or conversion["verification"]["source_verified"] is not True \
            or conversion["fixture_canonical_fingerprint"] != assembly["expected_fingerprint"] \
            or conversion["assembled"]["sha256"] != assembly["states"]["sha256"]:
        raise ValueError("Converted fixture is not the reviewed assembly")
    io.verify_artifacts({a.assembly / "states.pkl": assembly["states"]["sha256"],
                         a.state_rows / "states-rows.json": conversion["output"]["index"]["sha256"],
                         a.state_rows / "states-rows.bin": conversion["output"]["container"]["sha256"]})
    return dict(selection_stage_sha256=stage_sha, assembly_sha256=assembly_sha, conversion_receipt_sha256=conversion_sha,
                sets_sha256=stage["sets_sha256"]), sets, assembly, conversion


def compute(a):
    io.require_low_priority()
    pins, runtime = io.setup_runtime(a, bootstrap_runtime=False)
    chain, sets, assembly, conversion = verified_chain(a)
    from receipts import canonical
    from tier_backend import TierBackend
    a.output.mkdir(parents=True)
    manifest = io.work_bundle(a.output / "bundle", a.assembly / "states.pkl", a.state_rows, sets, a.v1, a.student)
    if (manifest["files"]["states.pkl"], manifest["files"]["states-rows.json"], manifest["files"]["states-rows.bin"]) != (
            assembly["states"]["sha256"], conversion["output"]["index"]["sha256"], conversion["output"]["container"]["sha256"]):
        raise ValueError("Work bundle files differ from the verified chain")
    started, clock = io.utc(), time.monotonic()
    backend = TierBackend(a.output / "bundle", a.runtime_root, a.native)  # the single setup_imports
    try:
        io.check_e4v3_modules()
        if set(backend.inputs) != set(sets["agreement"]):
            raise ValueError("Mac-profile backend must retain exactly the agreement inputs")
        refs = {}
        for number, identity in enumerate(sets["agreement"], 1):
            refs[identity], _ = backend.infer(identity, "cpu")
            if number % 250 == 0:
                print("student reference %d/%d" % (number, len(sets["agreement"])), flush=True)
        threads = dict(torch=backend.torch.get_num_threads(), interop=backend.torch.get_num_interop_threads())
    finally:
        backend.close()
    target = a.output / "student-reference.json"
    with target.open("x") as stream:
        stream.write(canonical(refs) + "\n")
    receipt = dict(schema="clasher.tiers-a4.student-reference.v1", utc_start=started, utc_end=io.utc(),
                   **io.process_identity(), versions=io.runtime_versions(), torch_threads=threads,
                   e4v3_pins=pins, runtime=runtime, **chain,
                   script_sha256={n: io.file_sha(io.HERE / n) for n in ("student_reference.py", "macreg_io.py")},
                   fixture_canonical_fingerprint=assembly["expected_fingerprint"], states_sha256=assembly["states"]["sha256"],
                   state_rows_index_sha256=conversion["output"]["index"]["sha256"],
                   state_rows_container_sha256=conversion["output"]["container"]["sha256"],
                   bundle_manifest_sha256=io.file_sha(a.output / "bundle" / "tiers-pins.json"),
                   bundle_files=manifest["files"], profile=manifest["profile"], states=len(refs),
                   student_reference=dict(file="student-reference.json", sha256=io.file_sha(target)),
                   seconds=time.monotonic() - clock, outcomes_read=False, timing=False)
    io.write_json(a.output / "student-reference-receipt.json", receipt)
    print(json.dumps(dict(states=len(refs), sha256=receipt["student_reference"]["sha256"])), flush=True)


def load_reference(reference, sets, stage_sha):
    """Current student-reference.json, bound to its receipt, keyed exactly by the agreement ids."""
    receipt_sha = io.file_sha(reference / "student-reference-receipt.json")
    receipt = json.loads((reference / "student-reference-receipt.json").read_text())
    refs = io.read_pinned_json(reference / "student-reference.json", receipt["student_reference"]["sha256"])
    if receipt["selection_stage_sha256"] != stage_sha or receipt["sets_sha256"] != io.sets_sha256(sets):
        raise ValueError("Student reference was computed for another selection")
    if set(refs) != set(sets["agreement"]) or len(refs) != len(sets["agreement"]):
        raise ValueError("Student reference keys must equal the agreement ids")
    return receipt_sha, receipt, refs


def check(a):
    pins = io.add_e4v3(a.e4v3 or Path(a.runtime_root) / io.E4V3_REL)
    from receipts import agreement
    from tier_backend import THRESHOLD
    stage_sha, stage, sets = selection_sets(a.selection)
    receipt_sha, receipt, refs = load_reference(a.reference, sets, stage_sha)
    end_speed = io.read_pinned_json(a.end_speed_reference, a.end_speed_reference_sha256)
    result = cross_check(refs, end_speed, sets["speed"]["S"], THRESHOLD, agreement)
    out = dict(schema="clasher.tiers-a4.student-cross-check.v1", utc=io.utc(), e4v3_pins=pins,
               end_speed_reference=dict(path=str(a.end_speed_reference), sha256=a.end_speed_reference_sha256),
               student_reference_receipt_sha256=receipt_sha, student_reference_sha256=receipt["student_reference"]["sha256"],
               selection_stage_sha256=stage_sha, **result, outcomes_read=False)
    io.write_json(a.reference / "student-cross-check.json", out)
    print(json.dumps({k: out[k] for k in ("passes", "states", "bit_exact", "max_abs_gate", "max_abs_logit")}), flush=True)
    if not result["passes"]:
        raise SystemExit("B.6 cross-check FAILED: recompute on 01 after its END pool")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("compute")
    io.runtime_arguments(c)
    for name in ("--selection", "--assembly", "--state-rows", "--v1", "--student", "--output"):
        c.add_argument(name, type=Path, required=True)
    k = sub.add_parser("cross-check")
    for name in ("--runtime-root", "--selection", "--reference", "--end-speed-reference"):
        k.add_argument(name, type=Path, required=True)
    k.add_argument("--e4v3", type=Path)
    k.add_argument("--end-speed-reference-sha256", required=True)
    a = p.parse_args(argv)
    (compute if a.command == "compute" else check)(a)


if __name__ == "__main__":
    main()
