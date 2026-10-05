"""Prepare a draft, enumerate declared work, or evaluate supplied branch receipts.

No collection or training is launched. This command does not freeze protocols:
real repetition/coverage studies and stable source pins belong to a later step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from clasher.rl.training_readiness_v2 import (
    APPROVED_STRATEGY_SHA,
    Branch,
    MechanismReview,
    Protocol,
    branch_plan,
    evaluate,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    draft = commands.add_parser("draft")
    draft.add_argument("--attempt-id", required=True)
    draft.add_argument("--strategy", type=Path, required=True)
    draft.add_argument("--consensus", type=Path, required=True)
    draft.add_argument("--output", type=Path, required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--protocol", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    assess = commands.add_parser("evaluate")
    assess.add_argument("--protocol", type=Path, required=True)
    assess.add_argument(
        "--branches", type=Path, required=True, help="JSONL branch records"
    )
    assess.add_argument("--reviews", type=Path, help="JSONL mechanism reviews")
    assess.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "draft":
        digest = hashlib.sha256(args.strategy.read_bytes()).hexdigest()
        consensus = json.loads(args.consensus.read_text())
        if digest != APPROVED_STRATEGY_SHA or consensus["sha256"] != digest:
            raise ValueError("strategy bytes differ from approved consensus")
        for member in ("astra", "fable"):
            if not consensus[member].get("approved_at"):
                raise ValueError("same-version approval is missing")
        result = Protocol(attempt_id=args.attempt_id).model_dump(mode="json")
    else:
        protocol = Protocol.model_validate_json(args.protocol.read_text())
        if args.command == "plan":
            result = {
                "status": protocol.status,
                "protocol_sha256": protocol.sha256,
                "branches": branch_plan(protocol),
            }
        else:
            branches = tuple(
                Branch.model_validate_json(line)
                for line in args.branches.read_text().splitlines()
                if line.strip()
            )
            reviews = (
                ()
                if args.reviews is None
                else tuple(
                    MechanismReview.model_validate_json(line)
                    for line in args.reviews.read_text().splitlines()
                    if line.strip()
                )
            )
            result = evaluate(protocol, branches, reviews).model_dump(mode="json")
    # Attempt artifacts are append-only: never replace an opened receipt.
    with args.output.open("x") as target:
        json.dump(result, target, indent=2)
        target.write("\n")


if __name__ == "__main__":
    main()
