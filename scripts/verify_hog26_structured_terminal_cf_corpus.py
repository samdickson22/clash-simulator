"""Verify the complete structured Hog 2.6 counterfactual corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from clasher.rl.counterfactual_corpus import terminal_candidate_order
from clasher.rl.recurrent_state_contract import (
    validate_action_time_recurrent_arrays,
)
from clasher.rl.strategy_bots import STRATEGY_NAMES

# Compatibility alias for verifier tests and downstream report tooling. The
# collector's authority must be the single source of truth for ordering.
STRATEGIES = STRATEGY_NAMES


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_split(
    root: Path,
    split: str,
    game_count: int,
    *,
    expected_contract: str = "public-actor-v1",
    minimum_phase_roots: dict[str, int] | None = None,
    expected_game_ids: set[int] | None = None,
) -> dict[str, Any]:
    report_path = root / f"{split}.json"
    arrays_path = root / f"{split}.npz"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("best_action_order") != "outcome-crowns-tower-damage-v1":
        raise ValueError(f"{split} terminal preference order changed")
    if report.get("structured_state_contract") != expected_contract:
        raise ValueError(f"{split} lost the public structured contract")
    if not isinstance(report.get("input_sha256"), dict):
        raise TypeError(f"{split} lost per-shard input authority")
    games = list(report["games"])
    if len(games) != game_count:
        raise ValueError(f"{split} game report count mismatch")
    game_ids = [int(row["game"]) for row in games]
    expected_game_ids = (
        set(range(game_count)) if expected_game_ids is None else expected_game_ids
    )
    if len(expected_game_ids) != game_count:
        raise ValueError(f"{split} expected game authority count mismatch")
    if set(game_ids) != expected_game_ids or len(set(game_ids)) != game_count:
        raise ValueError(f"{split} game coverage mismatch")
    expected_strategies = Counter(
        STRATEGIES[game % len(STRATEGIES)] for game in expected_game_ids
    )
    actual_strategies = Counter(str(row["strategy"]) for row in games)
    if any(
        str(row["strategy"])
        != STRATEGIES[int(row["game"]) % len(STRATEGIES)]
        for row in games
    ):
        raise ValueError(f"{split} strategy balance mismatch")
    if actual_strategies != expected_strategies:
        raise ValueError(f"{split} strategy balance mismatch")
    expected_seats = Counter(
        (game // len(STRATEGIES)) % 2 for game in expected_game_ids
    )
    actual_seats = Counter(int(row["controlled_player"]) for row in games)
    if any(
        int(row["controlled_player"])
        != (int(row["game"]) // len(STRATEGIES)) % 2
        for row in games
    ):
        raise ValueError(f"{split} candidate-seat balance mismatch")
    if actual_seats != expected_seats:
        raise ValueError(f"{split} candidate-seat balance mismatch")

    states = list(report["states"])
    states_collected = int(report["states_collected"])
    if len(states) != states_collected:
        raise ValueError(f"{split} state report count mismatch")
    state_keys = [(int(row["game"]), int(row["tick"])) for row in states]
    if len(state_keys) != len(set(state_keys)):
        raise ValueError(f"{split} contains duplicate decision roots")
    game_authority = {int(row["game"]): row for row in games}
    for row in states:
        authority = game_authority[int(row["game"])]
        if str(row["strategy"]) != str(authority["strategy"]) or int(
            row["controlled_player"]
        ) != int(authority["controlled_player"]):
            raise ValueError(f"{split} state/game authority mismatch")
    decisive = int(report["decisive_improvements"])
    base_wins = int(report["base_terminal_wins"])
    ticks = np.asarray([tick for _game, tick in state_keys], dtype=np.int64)
    if decisive / states_collected < 0.10:
        raise ValueError(f"{split} decisive-label rate is below ten percent")
    if not 0.10 <= base_wins / states_collected <= 0.90:
        raise ValueError(f"{split} base-outcome distribution is degenerate")

    with np.load(arrays_path, allow_pickle=False) as arrays:
        required = {
            "action_masks",
            "base_actions",
            "best_actions",
            "candidate_actions",
            "candidate_valid",
            "candidate_scores",
            "candidate_policy_logits",
            "candidate_policy_log_probabilities",
            "candidate_policy_type_log_probabilities",
            "candidate_card_features",
            "candidate_crown_differences",
            "candidate_tile_features",
            "candidate_tower_damage_differences",
            "features",
            "game_ids",
            "ticks",
            "structured_entity_ids",
            "structured_entity_features",
            "structured_entity_mask",
            "structured_hand_ids",
            "structured_global_features",
            "structured_previous_rewards",
        }
        if expected_contract == "public-actor-v2-action-time-recurrence":
            required.update(
                {
                    "structured_recurrent_cell",
                    "structured_previous_play_hazard",
                }
            )
        missing = sorted(required.difference(arrays.files))
        if missing:
            raise ValueError(f"{split} is missing arrays {missing}")
        if any(np.asarray(arrays[name]).shape[0] != states_collected for name in required):
            raise ValueError(f"{split} arrays are not state-aligned")
        if not np.array_equal(
            np.asarray(arrays["game_ids"], dtype=np.int64),
            np.asarray([game for game, _tick in state_keys], dtype=np.int64),
        ) or not np.array_equal(
            np.asarray(arrays["ticks"], dtype=np.int64),
            np.asarray([tick for _game, tick in state_keys], dtype=np.int64),
        ):
            raise ValueError(f"{split} array/report decision roots disagree")
        candidate_valid = np.asarray(arrays["candidate_valid"], dtype=np.bool_)
        candidate_actions = np.asarray(arrays["candidate_actions"], dtype=np.int64)
        if not np.array_equal(candidate_actions >= 0, candidate_valid):
            raise ValueError(f"{split} candidate validity disagrees with actions")
        if not candidate_valid[:, 0].all():
            raise ValueError(f"{split} contains an invalid base candidate")
        if int(candidate_valid.sum(axis=1).min()) < 2:
            raise ValueError(f"{split} contains a root without an intervention")
        rows = np.arange(states_collected)
        action_masks = np.asarray(arrays["action_masks"], dtype=np.bool_)
        base_actions = np.asarray(arrays["base_actions"], dtype=np.int64)
        best_actions = np.asarray(arrays["best_actions"], dtype=np.int64)
        for name, actions in (("base", base_actions), ("best", best_actions)):
            if np.any(actions < 0) or np.any(actions >= action_masks.shape[1]):
                raise ValueError(f"{split} contains an out-of-range {name} action")
            if not action_masks[rows, actions].all():
                raise ValueError(f"{split} contains an illegal {name} action")
        candidate_scores = np.asarray(arrays["candidate_scores"], dtype=np.float64)
        candidate_crowns = np.asarray(
            arrays["candidate_crown_differences"], dtype=np.int64
        )
        candidate_damage = np.asarray(
            arrays["candidate_tower_damage_differences"], dtype=np.float64
        )
        for row in rows.tolist():
            valid = np.flatnonzero(candidate_valid[row])
            orders = [
                terminal_candidate_order(
                    candidate_scores[row, index],
                    candidate_crowns[row, index],
                    candidate_damage[row, index],
                )
                for index in valid
            ]
            best_order = max(orders)
            canonical_best = (
                int(base_actions[row])
                if orders[0] == best_order
                else min(
                    int(candidate_actions[row, index])
                    for index, order in zip(valid, orders, strict=True)
                    if order == best_order
                )
            )
            if int(best_actions[row]) != canonical_best:
                raise ValueError(
                    f"{split} best action disagrees with terminal preference order"
                )
        if int(np.count_nonzero(best_actions != base_actions)) != decisive:
            raise ValueError(f"{split} decisive-label count disagrees with actions")
        if not np.array_equal(candidate_actions[:, 0], base_actions):
            raise ValueError(f"{split} candidate zero is not the base action")
        candidate_rows = np.broadcast_to(
            rows[:, None], candidate_actions.shape
        )[candidate_valid]
        if not action_masks[candidate_rows, candidate_actions[candidate_valid]].all():
            raise ValueError(f"{split} contains an illegal intervention candidate")
        hand_ids = np.asarray(arrays["structured_hand_ids"], dtype=np.int64)
        if hand_ids.shape[1] != 5 or np.any(hand_ids <= 1):
            raise ValueError(f"{split} lost a public hand or Next identity")
        entity_ids = np.asarray(arrays["structured_entity_ids"], dtype=np.int64)
        entity_mask = np.asarray(arrays["structured_entity_mask"], dtype=np.bool_)
        if np.any(entity_ids[entity_mask] <= 1) or np.any(entity_ids[~entity_mask] != 0):
            raise ValueError(f"{split} entity identity/mask padding disagrees")
        for name in (
            "features",
            "structured_entity_features",
            "structured_global_features",
            "structured_previous_rewards",
        ):
            if not np.isfinite(np.asarray(arrays[name])).all():
                raise ValueError(f"{split} contains non-finite {name}")
        for name in (
            "candidate_scores",
            "candidate_policy_logits",
            "candidate_policy_log_probabilities",
            "candidate_policy_type_log_probabilities",
            "candidate_card_features",
            "candidate_crown_differences",
            "candidate_tile_features",
            "candidate_tower_damage_differences",
        ):
            if not np.isfinite(np.asarray(arrays[name])[candidate_valid]).all():
                raise ValueError(f"{split} contains non-finite valid {name}")
        if expected_contract == "public-actor-v2-action-time-recurrence":
            validate_action_time_recurrent_arrays(
                arrays["structured_recurrent_cell"],
                arrays["structured_previous_play_hazard"],
                expected_rows=states_collected,
                expected_memory_size=64,
            )

    tick_coverage = {
        "minimum": int(ticks.min()),
        "maximum": int(ticks.max()),
        "early_lt_1200": int((ticks < 1200).sum()),
        "mid_1200_2399": int(((ticks >= 1200) & (ticks < 2400)).sum()),
        "late_regulation_2400_3599": int(
            ((ticks >= 2400) & (ticks < 3600)).sum()
        ),
        "overtime_ge_3600": int((ticks >= 3600).sum()),
    }
    if minimum_phase_roots is not None:
        for phase, minimum in minimum_phase_roots.items():
            if int(tick_coverage.get(phase, -1)) < int(minimum):
                raise ValueError(
                    f"{split} phase {phase} has fewer than {minimum} roots"
                )

    return {
        "games": game_count,
        "states": states_collected,
        "decisive_improvements": decisive,
        "decisive_rate": decisive / states_collected,
        "base_terminal_wins": base_wins,
        "base_terminal_win_rate": base_wins / states_collected,
        "tick_coverage": tick_coverage,
        "strategies": dict(sorted(actual_strategies.items())),
        "candidate_seats": {
            str(key): value for key, value in sorted(actual_seats.items())
        },
        "report_sha256": _sha256(report_path),
        "arrays_sha256": _sha256(arrays_path),
    }


def verify_corpus(root: Path) -> dict[str, Any]:
    return {
        "schema": "clasher.hog26_structured_terminal_cf_quality.v1",
        "root": str(root.resolve()),
        "train": verify_split(root, "train", 300),
        "validation": verify_split(root, "validation", 100),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify_corpus(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
