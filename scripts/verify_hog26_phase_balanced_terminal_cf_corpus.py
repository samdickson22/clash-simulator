"""Verify the frozen phase-balanced Hog 2.6 counterfactual corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.verify_hog26_structured_terminal_cf_corpus import verify_split


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root: Path, contract_path: Path) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("schema") != "clasher.hog26_phase_balanced_terminal_cf_contract.v1":
        raise ValueError("unsupported phase-balanced corpus contract")
    collection = dict(contract["collection"])
    minimum_roots = dict(contract["minimum_roots"])
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("structured_state_contract") != (
        "public-actor-v2-action-time-recurrence"
    ):
        raise ValueError("phase-balanced manifest lost recurrent public state")
    if manifest.get("best_action_order") != collection.get("best_action_order"):
        raise ValueError("phase-balanced terminal preference order changed")
    if manifest.get("query_schedule") != collection["query_schedule"] or tuple(
        int(value) for value in manifest.get("query_target_ticks", ())
    ) != tuple(collection["target_ticks"]):
        raise ValueError("phase-balanced manifest changed its tick schedule")
    expected_screen_hashes = {
        str(contract["launch_condition"]["overtime_train_screen_manifest_sha256"]),
        str(
            contract["launch_condition"][
                "overtime_validation_screen_manifest_sha256"
            ]
        ),
    }
    if set(dict(manifest.get("overtime_screen_inputs", {})).values()) != (
        expected_screen_hashes
    ):
        raise ValueError("phase-balanced overtime screen authority changed")
    expected_counts = {
        "train": int(collection["train_games"]),
        "validation": int(collection["validation_games"]),
    }
    expected_seeds = {
        "train": int(collection["train_seed"]),
        "validation": int(collection["validation_seed"]),
    }
    expected_input_hashes = {
        "train": {
            "policy": contract["policy"]["sha256"],
            "decks": contract["deck_authority"]["runtime_decks"]["sha256"],
            "outcome": None,
            "sampling_decks": None,
            "learner_sampling_decks": contract["deck_authority"]["learner"]["sha256"],
            "opponent_sampling_decks": contract["deck_authority"]["train_opponents"]["sha256"],
        },
        "validation": {
            "policy": contract["policy"]["sha256"],
            "decks": contract["deck_authority"]["runtime_decks"]["sha256"],
            "outcome": None,
            "sampling_decks": None,
            "learner_sampling_decks": contract["deck_authority"]["learner"]["sha256"],
            "opponent_sampling_decks": contract["deck_authority"]["validation_opponents"]["sha256"],
        },
    }
    expected_game_ids = {
        "train": set(range(int(collection["uniform_train_games"]))).union(
            int(value)
            for value in manifest["screened_overtime_game_ids"]["train"]
        ),
        "validation": set(
            range(int(collection["uniform_validation_games"]))
        ).union(
            int(value)
            for value in manifest["screened_overtime_game_ids"]["validation"]
        ),
    }
    expected_supplement_counts = {
        "train": int(collection["screened_overtime_train_games"]),
        "validation": int(collection["screened_overtime_validation_games"]),
    }
    if any(
        len(manifest["screened_overtime_game_ids"][split])
        != expected_supplement_counts[split]
        for split in ("train", "validation")
    ):
        raise ValueError("phase-balanced screened overtime selection count changed")
    split_results = {}
    for split in ("train", "validation"):
        report = json.loads((root / f"{split}.json").read_text(encoding="utf-8"))
        if report.get("input_sha256") != expected_input_hashes[split]:
            raise ValueError(f"{split} per-shard input authority changed")
        expected_overtime = int(
            collection[f"screened_overtime_{split}_games"]
        )
        if int(report.get("screened_overtime_states", -1)) != expected_overtime:
            raise ValueError(f"{split} screened overtime count changed")
        overtime_states = report["states"][-expected_overtime:]
        if any(int(row["tick"]) < 3600 for row in overtime_states):
            raise ValueError(f"{split} screened supplement is not overtime")
        for row in report["games"]:
            game = int(row["game"])
            if int(row["seed"]) != expected_seeds[split] + game * 1009:
                raise ValueError(f"{split} game seed authority changed")
        result = verify_split(
            root,
            split,
            expected_counts[split],
            expected_contract="public-actor-v2-action-time-recurrence",
            minimum_phase_roots=dict(minimum_roots[f"{split}_by_phase"]),
            expected_game_ids=expected_game_ids[split],
        )
        if int(result["states"]) < int(minimum_roots[f"{split}_total"]):
            raise ValueError(f"{split} total phase-balanced root gate failed")
        split_results[split] = result
    if contract["policy"]["sha256"] not in set(manifest["inputs"].values()):
        raise ValueError("phase-balanced manifest policy authority changed")
    return {
        "schema": "clasher.hog26_phase_balanced_terminal_cf_verification.v1",
        "status": "passed",
        "contract": str(contract_path.resolve()),
        "contract_sha256": _sha256(contract_path),
        "manifest": str(manifest_path.resolve()),
        "manifest_sha256": _sha256(manifest_path),
        **split_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.root, args.contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
