"""Collect one declared final stage after freezing every outcome candidate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.audit_hog26_outcome_corpora import audit
from scripts.audit_hog26_procedural_outcome_shard import shard_expectations
from scripts.collect_hog26_complete_outcomes import collect as collect_natural
from scripts.collect_hog26_symmetric_draw_outcomes import collect as collect_draw
from scripts.evaluate_hog26_frozen_outcome import validate_final_metadata
from scripts.freeze_hog26_outcome_cohort import load_frozen_cohort
from scripts.run_hog26_procedural_outcome_shard import collection_args
from scripts.train_hog26_actor_outcome import _atomic_json, file_sha256


def final_collection_args(protocol, role, *, root, device):
    stage = protocol["final_holdout"][role]
    if role == "generated":
        return collection_args(protocol, stage, root=root, device=device)
    common = {
        "checkpoint": root / protocol["base_policy"]["path"],
        "output": root / stage["output_corpus"],
        "report": root / stage["output_report"],
        "seed": stage["seed"], "device": device, "chunk_steps": 64,
    }
    if role == "controlled_draw":
        return argparse.Namespace(**common, battles=stage["battles"],
                                  episodes_per_battle=stage["episodes_per_battle"])
    if role != "reserved_original":
        raise ValueError("unknown final stage")
    return argparse.Namespace(
        **common, episodes_per_seat=stage["episodes_per_seat"],
        opponents=",".join(stage["opponents"]), opponent_decks=stage["deck"],
        opponent_deck_split="", opponent_family_id=(),
        supported_decks_path=root / protocol["original_decks"]["path"],
    )


def collect_final_stage(manifest_path, manifest_sha256, role, *, root, device):
    manifest, protocol, _ = load_frozen_cohort(manifest_path, manifest_sha256, root=root)
    stage = protocol["final_holdout"][role]
    args = final_collection_args(protocol, role, root=root, device=device)
    audit_path = root / stage["audit_report"]
    receipt_path = args.report.with_suffix(".collection-start.json")
    if any(path.exists() for path in (
        args.output.parent, args.report, audit_path, receipt_path,
    )):
        raise ValueError("final stage already started; refusing duplicate or overwrite")
    authority = {
        "frozen_cohort_sha256": manifest_sha256,
        "protocol_sha256": manifest["protocol_sha256"],
        "role": role, "seed": stage["seed"],
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.open("x") as handle:
        handle.write(json.dumps(authority, indent=2) + "\n")
    collector = collect_draw if role == "controlled_draw" else collect_natural
    report = collector(args)
    validate_final_metadata(protocol, role, report, root=root)
    if role == "generated":
        expected = shard_expectations(protocol, stage, root=root)
    elif role == "reserved_original":
        expected = {
            "expected_decks": {stage["deck"]},
            "expected_opponents": set(stage["opponents"]),
            "expected_supported_decks_sha256": protocol["original_decks"]["sha256"],
        }
    else:
        expected = {}
    audit_report = audit([args.output], **expected)
    count = stage["actor_views"] if role == "controlled_draw" else stage["expected_games"]
    if audit_report["status"] != "passed" or audit_report["episodes"] != count:
        raise ValueError("final stage audit failed the declared game budget")
    if (
        file_sha256(manifest_path) != manifest_sha256
        or file_sha256(Path(manifest["protocol"])) != manifest["protocol_sha256"]
    ):
        raise ValueError("final collection authority changed during collection")
    report["collection_authority"] = authority
    audit_report["collection_authority"] = authority
    _atomic_json(audit_path, audit_report)
    _atomic_json(args.report, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-cohort", type=Path, required=True)
    parser.add_argument("--frozen-cohort-sha256", required=True)
    parser.add_argument("--stage", choices=("generated", "reserved_original", "controlled_draw"), required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    args = parser.parse_args()
    collect_final_stage(args.frozen_cohort, args.frozen_cohort_sha256, args.stage,
                        root=Path.cwd(), device=args.device)


if __name__ == "__main__":
    main()
