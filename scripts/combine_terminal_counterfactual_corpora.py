"""Combine independently collected exact terminal intervention shards."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

ARRAY_NAMES = (
    "features",
    "action_masks",
    "base_actions",
    "best_actions",
    "candidate_actions",
    "candidate_scores",
    "candidate_valid",
    "candidate_kinds",
    "candidate_card_ids",
    "candidate_card_features",
    "candidate_tile_features",
    "candidate_policy_logits",
    "candidate_policy_log_probabilities",
    "candidate_policy_type_log_probabilities",
    "candidate_crown_differences",
    "candidate_tower_damage_differences",
    "candidate_terminal_ticks",
    "hand_ids",
    "game_ids",
    "ticks",
)

STRUCTURED_ARRAY_NAMES = (
    "structured_entity_ids",
    "structured_entity_features",
    "structured_entity_mask",
    "structured_hand_ids",
    "structured_global_features",
    "structured_opponent_history_ids",
    "structured_opponent_history_ages",
    "structured_opponent_seen_card_ids",
    "structured_previous_actions",
    "structured_previous_rewards",
    "structured_episode_starts",
)

STRUCTURED_V2_ARRAY_NAMES = (
    "structured_recurrent_cell",
    "structured_previous_play_hazard",
)


def _sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-root",
        type=Path,
        action="append",
        required=True,
    )
    parser.add_argument(
        "--pattern",
        default="*.npz",
        help="glob applied independently within every input root",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(
        {
            path
            for input_root in args.input_root
            for path in input_root.glob(args.pattern)
        }
    )
    if not paths:
        raise ValueError("no terminal counterfactual shards matched")
    arrays_by_name: dict[str, list[np.ndarray]] = {
        name: []
        for name in (
            *ARRAY_NAMES,
            *STRUCTURED_ARRAY_NAMES,
            *STRUCTURED_V2_ARRAY_NAMES,
        )
    }
    states: list[dict[str, Any]] = []
    games: list[dict[str, Any]] = []
    policies: set[str] = set()
    outcomes: set[str] = set()
    sampling_paths: set[str] = set()
    learner_sampling_paths: set[str] = set()
    opponent_sampling_paths: set[str] = set()
    semantic_versions: set[int] = set()
    semantic_sizes: set[int] = set()
    structured_state_contracts: set[str | None] = set()
    query_schedules: set[str] = set()
    query_target_ticks: set[tuple[int, ...]] = set()
    best_action_orders: set[str] = set()
    input_authorities: set[str] = set()
    collection_configs: set[str] = set()
    for path in paths:
        report_path = path.with_suffix(".json")
        if not report_path.is_file():
            raise ValueError(f"missing shard report {report_path}")
        report = json.loads(report_path.read_text())
        if int(report.get("schema_version", 0)) != 2:
            raise ValueError(f"unsupported terminal counterfactual schema in {report_path}")
        policies.add(str(report["policy"]))
        outcomes.add(str(report["outcome"]))
        sampling_paths.add(str(report["sampling_decks_path"]))
        learner_sampling_paths.add(str(report["learner_sampling_decks_path"]))
        opponent_sampling_paths.add(str(report["opponent_sampling_decks_path"]))
        semantic_versions.add(int(report["candidate_card_semantics_version"]))
        semantic_sizes.add(int(report["candidate_card_feature_size"]))
        structured_state_contracts.add(report.get("structured_state_contract"))
        query_schedules.add(str(report.get("query_schedule", "first-eligible")))
        query_target_ticks.add(
            tuple(int(value) for value in report.get("query_target_ticks", ()))
        )
        best_action_orders.add(str(report.get("best_action_order")))
        input_authorities.add(
            json.dumps(report.get("input_sha256"), sort_keys=True)
        )
        collection_configs.add(
            json.dumps(report.get("collection_config"), sort_keys=True)
        )
        states.extend(report["states"])
        games.extend(report["games"])
        with np.load(path, allow_pickle=False) as payload:
            for name in ARRAY_NAMES:
                if name in payload.files:
                    array = np.asarray(payload[name])
                elif name == "game_ids":
                    array = np.asarray(
                        [int(row["game"]) for row in report["states"]],
                        dtype=np.int64,
                    )
                elif name == "ticks":
                    array = np.asarray(
                        [int(row["tick"]) for row in report["states"]],
                        dtype=np.int64,
                    )
                else:
                    raise ValueError(f"missing terminal counterfactual array {name}")
                arrays_by_name[name].append(array)
            if report.get("structured_state_contract") is not None:
                for name in STRUCTURED_ARRAY_NAMES:
                    if name not in payload.files:
                        raise ValueError(
                            f"missing structured counterfactual array {name}"
                        )
                    arrays_by_name[name].append(np.asarray(payload[name]))
            if report.get("structured_state_contract") == (
                "public-actor-v2-action-time-recurrence"
            ):
                for name in STRUCTURED_V2_ARRAY_NAMES:
                    if name not in payload.files:
                        raise ValueError(
                            f"missing structured v2 counterfactual array {name}"
                        )
                    arrays_by_name[name].append(np.asarray(payload[name]))
    if (
        len(policies) != 1
        or len(outcomes) != 1
        or len(semantic_versions) != 1
        or len(semantic_sizes) != 1
        or len(learner_sampling_paths) != 1
        or len(opponent_sampling_paths) != 1
        or len(structured_state_contracts) != 1
        or len(query_schedules) != 1
        or len(query_target_ticks) != 1
        or best_action_orders != {"outcome-crowns-tower-damage-v1"}
        or len(input_authorities) != 1
        or len(collection_configs) != 1
    ):
        raise ValueError("terminal counterfactual shard authorities do not match")
    structured_state_contract = next(iter(structured_state_contracts))
    if structured_state_contract not in {
        None,
        "public-actor-v1",
        "public-actor-v2-action-time-recurrence",
    }:
        raise ValueError("unsupported structured counterfactual state contract")
    state_keys = [(int(row["game"]), int(row["tick"])) for row in states]
    if len(state_keys) != len(set(state_keys)):
        raise ValueError("duplicate terminal counterfactual state keys")
    selected_array_names = (
        (*ARRAY_NAMES, *STRUCTURED_ARRAY_NAMES, *STRUCTURED_V2_ARRAY_NAMES)
        if structured_state_contract == "public-actor-v2-action-time-recurrence"
        else (*ARRAY_NAMES, *STRUCTURED_ARRAY_NAMES)
        if structured_state_contract is not None
        else ARRAY_NAMES
    )
    arrays = {
        name: np.concatenate(parts, axis=0)
        for name in selected_array_names
        for parts in (arrays_by_name[name],)
    }
    row_count = len(states)
    if any(array.shape[0] != row_count for array in arrays.values()):
        raise ValueError("terminal counterfactual report and array rows disagree")
    if not np.array_equal(arrays["candidate_actions"] >= 0, arrays["candidate_valid"]):
        raise ValueError("terminal counterfactual candidate validity disagrees")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as handle:
        np.savez_compressed(handle, **arrays)  # type: ignore[arg-type]
    combined = {
        "schema_version": 2,
        "policy": next(iter(policies)),
        "outcome": next(iter(outcomes)),
        "candidate_card_semantics_version": next(iter(semantic_versions)),
        "candidate_card_feature_size": next(iter(semantic_sizes)),
        "best_action_order": next(iter(best_action_orders)),
        "input_sha256": json.loads(next(iter(input_authorities))),
        "collection_config": json.loads(next(iter(collection_configs))),
        "structured_state_contract": structured_state_contract,
        "query_schedule": next(iter(query_schedules)),
        "query_target_ticks": list(next(iter(query_target_ticks))),
        "sampling_decks_path": (
            next(iter(sampling_paths)) if len(sampling_paths) == 1 else None
        ),
        "sampling_decks_paths": sorted(sampling_paths),
        "learner_sampling_decks_path": next(iter(learner_sampling_paths)),
        "opponent_sampling_decks_path": next(iter(opponent_sampling_paths)),
        "shards": len(paths),
        "states_collected": row_count,
        "decisive_improvements": sum(
            bool(row["decisive_improvement"]) for row in states
        ),
        "base_terminal_wins": sum(float(row["base_score"]) == 1.0 for row in states),
        "array_shapes": {name: list(array.shape) for name, array in arrays.items()},
        "array_sha256": {name: _sha256(array) for name, array in arrays.items()},
        "output": str(args.output.resolve()),
        "source_shards": [str(path.resolve()) for path in paths],
        "games": sorted(games, key=lambda row: int(row["game"])),
        # State order intentionally matches every concatenated array row.
        "states": states,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(combined, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                key: combined[key]
                for key in (
                    "shards",
                    "states_collected",
                    "decisive_improvements",
                    "base_terminal_wins",
                    "array_sha256",
                )
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
