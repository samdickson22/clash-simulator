"""Measure eight fresh worker processes while preserving exact preflight trajectories."""

import json
import os
import subprocess
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import psutil
from expansion_protocol import preflight_schedules
from parallel_engine import fingerprint, initialize
from probe_worker import sha

from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata


def main():
    began = time.monotonic()
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_parallel_collection_probe8_20260913"
    if output.exists():
        raise ValueError("preserve existing parallel replay")
    base_directory = root / "datasets/derived/hog26_training_expansion_preflight_20260913"
    complete_path, base_plan_path = base_directory / "complete.json", base_directory / "run_plan.json"
    base_plan, complete = json.loads(base_plan_path.read_text()), json.loads(complete_path.read_text())
    pin_path = root / "reports/hog26_training_expansion_preflight_pin_20260913.json"
    pin = json.loads(pin_path.read_text())
    if (complete["status"] != "complete-audited" or complete["mode"] != "preflight" or complete["game_count"] != 12
            or pin["evidence"][str(complete_path)] != sha(complete_path)):
        raise ValueError("independently audited sequential preflight required")
    records = {row["path"]: row for row in complete["games"]}
    resources = {key: value["path"] for key, value in base_plan["source_authority"]["resources"].items()}
    resources.update(parallel_base_complete=complete_path, parallel_base_plan=base_plan_path, parallel_preflight_pin=pin_path)
    for directory in (Path(__file__).parent, root / "experiments/hog26_parallel_collection_probe"):
        for path in directory.glob("*.py"):
            resources[str(path.relative_to(root))] = path
    cases = []
    for index, schedule in enumerate(preflight_schedules(base_plan)):
        for scenario in audit_scalar_opening_metadata(schedule["metadata"], expected_authority=schedule["external_authority"]):
            for seat in schedule["learner_seats"]:
                name = f"game-{index:03d}-{scenario.ordinal:03d}-{seat}.npz"
                reference = base_directory / name
                if sha(reference) != records[name]["sha256"]:
                    raise ValueError("sequential preflight archive changed")
                resources[f"parallel_reference_{len(cases)}"] = reference
                cases.append({"name": name, "schedule": schedule, "ordinal": scenario.ordinal, "seat": seat,
                              "reference_path": str(reference), "reference_sha256": records[name]["sha256"]})
    if len(cases) != 12 or {c["name"] for c in cases} != set(records):
        raise ValueError("parallel preflight case inventory differs")
    engine = initialize(root, base_plan["source_authority"]["contract"]["canonical_names"])
    authority = fingerprint(engine, resources)
    plan = {"schema": "clasher.parallel-preflight-replay.v1", "workers": 8,
            "source_authority": authority, "cases": cases, "fitting": False, "acceptance": False,
            "scope": "Exact replay of all excluded preflight cases; this creates no training games."}
    output.mkdir()
    plan_path = output / "plan.json"
    with plan_path.open("x") as stream:
        json.dump(plan, stream, indent=2)
        stream.write("\n")
    environment = dict(os.environ, OMP_NUM_THREADS="1",
                       PYTHONPATH="experiments/hog26_parallel_collection_probe:experiments/hog26_training_expansion:experiments/hog26_scalar_pilot:src:.")

    def run_case(index):
        started = time.monotonic()
        with (output / f"worker-{index:03d}.log").open("x") as log:
            result = subprocess.run(["/Users/sam/Desktop/code/clasher/.venv/bin/python", "-u",
                                     "experiments/hog26_parallel_collection_probe/probe_worker.py",
                                     "--plan", str(plan_path), "--case", str(index), "--output", str(output)],
                                    cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT, check=False)
        return {"case": index, "exit_code": result.returncode, "process_seconds": time.monotonic() - started}

    execution_started = time.monotonic()
    peak, outcomes = 0, []
    with ThreadPoolExecutor(max_workers=8) as pool:
        pending = {pool.submit(run_case, index) for index in range(12)}
        while pending:
            done, pending = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
            process = psutil.Process()
            try:
                peak = max(peak, process.memory_info().rss + sum(c.memory_info().rss for c in process.children(recursive=True)))
            except psutil.NoSuchProcess:
                pass
            if peak > 18 * 1024**3:
                for child in process.children(recursive=True):
                    child.terminate()
                raise MemoryError("parallel replay exceeded 18 GiB combined process RSS")
            for future in done:
                row = future.result()
                outcomes.append(row)
                print(json.dumps({"completed_cases": len(outcomes), **row}), flush=True)
    seconds = time.monotonic() - execution_started
    if any(row["exit_code"] != 0 for row in outcomes):
        raise ValueError("parallel replay case failed; preserve all evidence")
    receipts = [json.loads((output / f"receipt-{index:03d}.json").read_text()) for index in range(12)]
    if any(not row["arrays_exact"] for row in receipts) or fingerprint(engine, resources) != authority:
        raise ValueError("parallel replay parity or source check failed")
    result = {"status": "parallel-preflight-parity-complete", "games": 12, "workers": 8,
              "all_arrays_exact_except_provenance_metadata": True, "plan_sha256": sha(plan_path),
              "parallel_execution_seconds": seconds, "total_seconds_from_main": time.monotonic() - began,
              "peak_combined_rss_bytes": peak, "receipts": receipts, "process_outcomes": sorted(outcomes, key=lambda r: r["case"]),
              "fitting": False, "acceptance": False,
              "limitations": ["Twelve excluded cases establish bounded replay parity, not full simulator acceptance.",
                              "Production parallel collection needs its own frozen authority and complete-game audit.",
                              "The original sequential collector continues unchanged during this probe."]}
    with (output / "complete.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: result[k] for k in ("status", "parallel_execution_seconds", "peak_combined_rss_bytes")}), flush=True)


if __name__ == "__main__":
    main()
