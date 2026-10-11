#!/usr/bin/env python3
"""TIERS Amendment 4 blocking memory check (Mac profile, offline on 05; not timing).

Mirrors the Mac session's resident backends on the student-reference work bundle:
the main TierBackend (which runs D2 over the whole agreement set) and D6's two
sequential spawned ``forward_worker`` backends. Each backend must retain exactly the
agreement policy inputs (>= 2,000 unique ids); each child runs a cold forward plus
2,000 forwards over ``agreement[:2000]``, as forward_worker does. Gate: main VmHWM +
child-1 VmHWM + child-2 VmHWM <= 6 GiB, a conservative sum of the measured processes
since the children never coexist. Linux CPU RSS is a proxy for macOS CPU/MPS memory
footprint, not an upper bound for it; the Mac session's own receipts remain binding.
Each interpreter's runtime is bootstrapped once, by its TierBackend.
"""
import argparse
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import macreg_io as io

CAP_BYTES = 6 * 2**30
FORWARDS = 2000


def ids_sha256(ids):
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


def child(args, bundle, ids, output):
    io.setup_runtime(args, bootstrap_runtime=False)
    from tier_backend import TierBackend
    backend = TierBackend(bundle, args.runtime_root, args.native)
    try:
        io.check_e4v3_modules()
        constructed = io.memory_status()
        forwards = 0
        for identity in [ids[0]] + ids:  # cold forward, then every registered forward (forward_worker)
            backend.infer(identity, "cpu")
            forwards += 1
        Path(output).write_text(json.dumps(dict(after_construction=constructed, after_forwards=io.memory_status(),
                                                inputs_retained=len(backend.inputs),
                                                inputs_retained_sha256=ids_sha256(backend.inputs), forwards=forwards)))
    finally:
        backend.close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    io.runtime_arguments(p)
    for name in ("--selection", "--reference", "--output"):
        p.add_argument(name, type=Path, required=True)
    a = p.parse_args(argv)
    io.require_low_priority()
    a.output.mkdir(parents=True)
    pins, runtime = io.setup_runtime(a, bootstrap_runtime=False)
    from student_reference import load_reference, selection_sets
    stage_sha, stage, sets = selection_sets(a.selection)
    reference_sha, reference, _ = load_reference(a.reference, sets, stage_sha)
    bundle = a.reference / "bundle"
    manifest_sha = io.file_sha(bundle / "tiers-pins.json")
    manifest = json.loads((bundle / "tiers-pins.json").read_text())
    if manifest_sha != reference["bundle_manifest_sha256"] or manifest["profile"] != "mac-preregistered" \
            or io.sets_sha256(manifest["sets"]) != stage["sets_sha256"]:
        raise ValueError("Memory check bundle is not the reviewed Mac-profile student-reference bundle")
    io.verify_artifacts({bundle / name: manifest["files"][name] for name in ("states.pkl", "states-rows.json", "states-rows.bin")})
    agreement = manifest["sets"]["agreement"]
    if len(agreement) < FORWARDS or len(set(agreement)) != len(agreement):
        raise ValueError("Memory check needs >= 2,000 unique agreement ids")
    expected_retained = ids_sha256(agreement)
    from tier_backend import TierBackend
    started, clock = io.utc(), time.monotonic()
    backend = TierBackend(bundle, a.runtime_root, a.native)  # the single setup_imports in this process
    try:
        io.check_e4v3_modules()
        if set(backend.inputs) != set(agreement):
            raise ValueError("Main backend must retain exactly the agreement inputs")
        main_constructed = io.memory_status()
        d2 = 0
        for identity in agreement:  # D2 student_agreement in the main process
            backend.infer(identity, "cpu")
            d2 += 1
        main_after_d2 = io.memory_status()
        children, concurrent = [], 0
        context = mp.get_context("spawn")
        for number in (1, 2):
            output = a.output / ("child-%d.json" % number)
            worker = context.Process(target=child, args=(a, bundle, agreement[:FORWARDS], output))
            worker.start()
            while worker.is_alive():
                try:
                    concurrent = max(concurrent, io.memory_status()["VmRSS"] + io.memory_status(worker.pid)["VmRSS"])
                except (FileNotFoundError, ProcessLookupError, KeyError):
                    pass
                worker.join(.05)
            if worker.exitcode != 0:
                raise RuntimeError("D6 child %d failed" % number)
            report = json.loads(output.read_text())
            if report["inputs_retained_sha256"] != expected_retained or report["forwards"] != FORWARDS + 1:
                raise ValueError("D6 child %d did not run the registered workload" % number)
            children.append(report)
        main_final = io.memory_status()
    finally:
        backend.close()
    conservative = main_final["VmHWM"] + sum(c["after_forwards"]["VmHWM"] for c in children)
    receipt = dict(schema="clasher.tiers-a4.mac-profile-memory.v1", utc_start=started, utc_end=io.utc(),
                   **io.process_identity(), versions=io.runtime_versions(), e4v3_pins=pins, runtime=runtime,
                   script_sha256={n: io.file_sha(io.HERE / n) for n in ("memory_check.py", "macreg_io.py")},
                   selection_stage_sha256=stage_sha, sets_sha256=stage["sets_sha256"],
                   student_reference_receipt_sha256=reference_sha, bundle_manifest_sha256=manifest_sha,
                   states_sha256=manifest["files"]["states.pkl"], state_rows_index_sha256=manifest["files"]["states-rows.json"],
                   state_rows_container_sha256=manifest["files"]["states-rows.bin"],
                   agreement=len(agreement), inputs_retained_main=len(agreement), inputs_retained_sha256=expected_retained,
                   d2_forwards_main=d2, forwards_per_child=FORWARDS + 1,
                   main=dict(after_construction=main_constructed, after_d2=main_after_d2, final=main_final),
                   children=children, sampled_concurrent_vmrss_peak_bytes=concurrent,
                   conservative_sum_vmhwm_bytes=conservative, cap_bytes=CAP_BYTES, passes=conservative <= CAP_BYTES,
                   seconds=time.monotonic() - clock,
                   caveat="Linux CPU RSS on 05 is a proxy for macOS CPU/MPS footprint, not an upper bound; no Mac contact",
                   outcomes_read=False, timing=False)
    io.write_json(a.output / "mac-profile-memory.json", receipt)
    print(json.dumps({k: receipt[k] for k in ("conservative_sum_vmhwm_bytes", "sampled_concurrent_vmrss_peak_bytes", "passes")}), flush=True)
    if not receipt["passes"]:
        raise SystemExit("Mac-profile memory check FAILED")


if __name__ == "__main__":
    main()
