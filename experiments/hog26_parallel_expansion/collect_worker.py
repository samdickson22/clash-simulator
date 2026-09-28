"""Run one fixed complete game with the already parity-tested engine."""

import argparse
import json
import os
from pathlib import Path

from parallel_engine import compare_arrays, fingerprint, initialize, play
from parallel_io import publish_archive, publish_json
from parallel_protocol import case_at, expected_metadata
from probe_worker import sha

from scripts.hog26_scalar_corpus import validate_scalar_corpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--mode", choices=("preflight", "collect"), required=True)
    parser.add_argument("--case", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    if args.mode == "collect" and (not plan["frozen"] or not plan["collection_allowed"]):
        raise ValueError("parallel collection requires frozen preflight authority")
    case = case_at(plan, args.mode, args.case)
    final = args.output / case["name"]
    temporary = args.output / f".pending-{args.case:04d}-{os.getpid()}.npz"
    root = Path(__file__).resolve().parents[2]
    engine = initialize(root, plan["source_authority"]["contract"]["canonical_names"])
    resources = {key: value["path"] for key, value in plan["source_authority"]["resources"].items()}
    if fingerprint(engine, resources) != plan["source_authority"]:
        raise ValueError("parallel worker authority differs")
    metadata_expected = expected_metadata(engine, plan, case, args.mode)
    if final.exists():
        audit = validate_scalar_corpus(final, expected_metadata=metadata_expected)
        archive = final
    else:
        if temporary.exists():
            raise ValueError("preserve existing temporary game evidence")
        audit = play(engine, plan=plan, case=case, path=temporary, mode=args.mode)
        archive = temporary
    if audit["metadata"] != metadata_expected:
        raise ValueError("parallel worker metadata differs from independent schedule")
    if any(audit[key] for key in ("rejected_card_actions", "noop_false_results", "failed_ability_actions")):
        raise ValueError("parallel game contains rejected or failed actions")
    fields = None
    if args.mode == "preflight":
        reference = root / "datasets/derived/hog26_training_expansion_preflight_20260913" / case["name"]
        fields = compare_arrays(reference, archive)
    metadata = audit.pop("metadata")
    row = {"path": final.name, "sha256": sha(archive),
           **{key: metadata[key] for key in ("family_id", "style", "learner_seat", "scenario_id", "cluster_id")}, **audit}
    if archive != final:
        publish_archive(temporary, final)
    if fingerprint(engine, resources) != plan["source_authority"]:
        raise ValueError("parallel worker source changed before publication")
    publish_json(final.with_suffix(".audit.json"), row)
    publish_json(args.output / f"receipt-{args.case:04d}.json", {"case": args.case, "record": row,
                                                                 "preflight_parity_fields": fields})


if __name__ == "__main__":
    main()
