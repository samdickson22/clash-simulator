"""Preserve and later compare the retired sequential execution prefix."""

import argparse
import fcntl
import json
from pathlib import Path

from parallel_engine import compare_arrays, fingerprint, initialize
from parallel_io import publish_json
from parallel_protocol import BASE_PLAN, case_at, expected_metadata
from probe_worker import sha

from scripts.hog26_scalar_corpus import validate_scalar_corpus


def snapshot(root):
    output = root / "reports/hog26_training_expansion_sequential_retired_prefix_20260913.json"
    if output.exists():
        raise ValueError("preserve existing retired prefix snapshot")
    directory = root / "datasets/derived/hog26_training_expansion_seed1280101_20260913"
    lease = (directory / ".collector.lock").open("a")
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    plan_path = root / BASE_PLAN
    plan = json.loads(plan_path.read_text())
    engine = initialize(root, plan["source_authority"]["contract"]["canonical_names"])
    resources = {key: value["path"] for key, value in plan["source_authority"]["resources"].items()}
    if fingerprint(engine, resources) != plan["source_authority"]:
        raise ValueError("retired sequential source authority differs")
    records = []
    for index in range(4608):
        case = case_at(plan, "collect", index)
        path = directory / case["name"]
        audit_path = path.with_suffix(".audit.json")
        if not audit_path.exists():
            break
        record = json.loads(audit_path.read_text())
        if sha(path) != record["sha256"]:
            raise ValueError("retired sequential archive changed")
        audit = validate_scalar_corpus(path, expected_metadata=expected_metadata(engine, plan, case, "collect"))
        metadata = audit.pop("metadata")
        recomputed = {"path": path.name, "sha256": sha(path),
                      **{key: metadata[key] for key in ("family_id", "style", "learner_seat", "scenario_id", "cluster_id")}, **audit}
        if recomputed != record:
            raise ValueError("retired sequential audit does not reproduce")
        records.append({"path": str(path), "sha256": record["sha256"], "record": record})
    expected_audits = {Path(row["path"]).with_suffix(".audit.json").name for row in records}
    if {p.name for p in directory.glob("game-*.audit.json")} != expected_audits:
        raise ValueError("retired sequential completed games are not a contiguous prefix")
    unverified = sorted({p.name for p in directory.glob("game-*.npz")} - {Path(row["path"]).name for row in records})
    publish_json(output, {"status": "audited-retired-sequential-prefix", "games": len(records), "input_games": records,
                          "unverified_tail_files_preserved": unverified, "source_plan_sha256": sha(plan_path),
                          "source_sha256": sha(__file__), "fitting_allowed": False,
                          "scope": "Preserved execution evidence only; this is not a completed training corpus. No game was selected by outcome."})
    print(json.dumps({"status": "audited-retired-sequential-prefix", "games": len(records), "unverified_tail_files": len(unverified)}), flush=True)


def compare(root):
    snapshot_path = root / "reports/hog26_training_expansion_sequential_retired_prefix_20260913.json"
    prefix = json.loads(snapshot_path.read_text())
    directory = root / "datasets/derived/hog26_training_expansion_parallel_seed1280101_20260913"
    completion_path = directory / "complete.json"
    completion = json.loads(completion_path.read_text())
    if completion["status"] != "complete-audited" or completion["mode"] != "collect" or completion["game_count"] != 4608:
        raise ValueError("complete parallel expansion required for prefix comparison")
    output = root / "reports/hog26_training_expansion_sequential_prefix_parity_20260913.json"
    if output.exists():
        raise ValueError("preserve existing prefix parity review")
    records = {row["path"]: row for row in completion["games"]}
    compared = []
    for item in prefix["input_games"]:
        original = Path(item["path"])
        parallel = directory / original.name
        if sha(original) != item["sha256"] or sha(parallel) != records[original.name]["sha256"]:
            raise ValueError("prefix comparison archive changed")
        fields = compare_arrays(original, parallel)
        compared.append({"path": original.name, "fields": fields, "exact": True})
    publish_json(output, {"status": "retired-prefix-array-parity-passed", "games": len(compared),
                          "all_arrays_exact_except_provenance_metadata": True, "comparisons": compared,
                          "prefix_manifest_sha256": sha(snapshot_path), "parallel_complete_sha256": sha(completion_path),
                          "source_sha256": sha(__file__), "acceptance": False,
                          "scope": "Execution parity only; complete combined data and memory audits remain required before fitting."})
    print(json.dumps({"status": "retired-prefix-array-parity-passed", "games": len(compared)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("snapshot", "compare"), required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    snapshot(root) if args.mode == "snapshot" else compare(root)


if __name__ == "__main__":
    main()
