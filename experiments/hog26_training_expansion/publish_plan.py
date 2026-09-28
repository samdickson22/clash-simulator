"""Audit the excluded expansion preflight and publish collection-only authority."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import torch
from expansion_protocol import (
    build_pilot_plan,
    preflight_schedules,
    source_fingerprint,
    validate_pilot_plan,
)

from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from scripts.evaluate_hog26_simple_policy import load_model
from scripts.hog26_scalar_corpus import validate_scalar_corpus
from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata
from scripts.hog26_scalar_openings import digest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_preflight(directory, authority, draft):
    complete_path = directory / "complete.json"
    complete = json.loads(complete_path.read_text())
    if (complete.get("status") != "complete-audited" or complete.get("mode") != "preflight"
            or complete.get("game_count") != 12 or len(complete.get("games", [])) != 12
            or complete.get("source_authority_sha256") != digest(authority)
            or complete.get("plan_sha256") != digest(draft)
            or json.loads((directory / "run_plan.json").read_text()) != draft):
        raise ValueError("complete matching twelve-game expansion preflight required")
    records = {row["path"]: row for row in complete["games"]}
    if len(records) != 12 or set(records) != {p.name for p in directory.glob("game-*.npz")}:
        raise ValueError("preflight artifact inventory differs")
    seen, clusters, rows = set(), set(), 0
    for index, schedule in enumerate(preflight_schedules(draft)):
        scenarios = audit_scalar_opening_metadata(schedule["metadata"], expected_authority=schedule["external_authority"])
        for scenario in scenarios:
            for seat in schedule["learner_seats"]:
                name = f"game-{index:03d}-{scenario.ordinal:03d}-{seat}.npz"
                path = directory / name
                record = records[name]
                if sha(path) != record["sha256"]:
                    raise ValueError("preflight archive changed")
                audit = validate_scalar_corpus(path)
                metadata = audit.pop("metadata")
                expected = {"mode": "preflight", "source_authority_sha256": digest(authority),
                            "plan_sha256": digest(draft), "opening_metadata": schedule["metadata"],
                            "opening_authority": schedule["external_authority"], "learner_seat": seat,
                            "scenario_id": scenario.scenario_id, "cluster_id": scenario.cluster_id,
                            "ordinal": scenario.ordinal, "family_id": schedule["family_id"],
                            "style": schedule["external_authority"]["opponent_style"]}
                if any(metadata.get(key) != value for key, value in expected.items()):
                    raise ValueError("preflight metadata differs from independent schedule")
                recomputed = {"path": name, "sha256": sha(path), "family_id": schedule["family_id"],
                              "style": expected["style"], "learner_seat": seat,
                              "scenario_id": scenario.scenario_id, "cluster_id": scenario.cluster_id, **audit}
                if recomputed != record or json.loads(path.with_suffix(".audit.json").read_text()) != record:
                    raise ValueError("preflight audit record does not reproduce")
                if any(audit[key] != 0 for key in ("rejected_card_actions", "noop_false_results", "failed_ability_actions")):
                    raise ValueError("preflight contains rejected or failed actions")
                with np.load(path, allow_pickle=False) as archive:
                    if not bool(archive["actual_terminal"]):
                        raise ValueError("preflight did not reach an actual terminal")
                seen.add(name)
                clusters.add(scenario.cluster_id)
                rows += audit["rows"]
    if seen != set(records) or len(clusters) != 6 or rows != complete["rows"]:
        raise ValueError("preflight quota or row total differs")
    return {"status": "passed", "source_authority_sha256": digest(authority),
            "evidence": {str(complete_path.resolve()): sha(complete_path)},
            "preflight_clusters": sorted(clusters),
            "checks": {"games": 12, "clusters": 6, "rows": rows, "all_actual_terminal": True,
                       "zero_rejected_actions": True, "source_unchanged": True},
            "scope": "Collection of 4608 complete training games only; no fitting, reserved collection or promotion."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-dir", type=Path, required=True)
    parser.add_argument("--pin", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    if args.pin.exists() or args.plan.exists():
        raise ValueError("preserve existing expansion authority")
    root = Path(__file__).resolve().parents[2]
    if shutil.disk_usage(root).free < 20 * 1024**3:
        raise ValueError("expansion requires at least 20 GiB free for data and separately gated feature work")
    torch.set_num_threads(1)
    checkpoint = root / "checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt"
    _, builder = load_model(checkpoint, torch.device("cpu"))
    vocabulary = load_current_client_typed_vocabulary()
    authority = source_fingerprint(root, resource_paths={"checkpoint": checkpoint, "card_data": Path(builder.loader.data_file)},
                                   vocabulary_sha256=vocabulary.sha256, card_definitions=builder.loader.load_card_definitions())
    draft = build_pilot_plan(authority=authority)
    pin = audit_preflight(args.preflight_dir, authority, draft)
    plan = build_pilot_plan(authority=authority, preflight=pin)
    validate_pilot_plan(plan, authority, expected_preflight=pin)
    for path, value in ((args.pin, pin), (args.plan, plan)):
        with path.open("x") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
    print(json.dumps({"status": "frozen-collection-only", "games": 4608,
                      "plan_sha256": sha(args.plan), "preflight_pin_sha256": sha(args.pin)}), flush=True)


if __name__ == "__main__":
    main()
