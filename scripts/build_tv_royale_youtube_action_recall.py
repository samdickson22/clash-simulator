from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.extract_tv_royale_youtube_fullmatch import _atomic_json, _sha256

SCHEMA = "clasher.youtube.cached_action_labels.v1"
GOLD_SCHEMA = "clasher.youtube.action_gold.v1"


def _rows(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _card_authority(vocabulary: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(vocabulary.read_text())
    return {
        str(row["stable_key"]): row
        for row in payload["entries"]
        if row["namespace"] == "card_action"
    }


def _elixir_drop_groups(
    rows: list[dict[str, Any]], player_id: int
) -> list[dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    previous: tuple[int, int, float] | None = None
    for index, row in enumerate(rows):
        head = row["offline_privileged_hud"][str(player_id)]["elixir"]
        if not head["valid"]:
            previous = None
            continue
        timestamp = int(row["timestamp_ms"])
        value = float(head["value"])
        if previous is not None and timestamp - previous[1] <= 200:
            drop = previous[2] - value
            if drop >= 0.50:
                raw.append(
                    {
                        "start_index": previous[0],
                        "end_index": index,
                        "timestamp_ms": timestamp,
                        "drop": drop,
                    }
                )
        previous = (index, timestamp, value)

    groups: list[list[dict[str, Any]]] = []
    for item in raw:
        if groups and item["timestamp_ms"] - groups[-1][-1]["timestamp_ms"] <= 150:
            groups[-1].append(item)
        else:
            groups.append([item])
    return [
        {
            "player_id": player_id,
            "start_index": group[0]["start_index"],
            "end_index": group[-1]["end_index"],
            "timestamp_ms": group[-1]["timestamp_ms"],
            "observed_elixir_drop": sum(float(item["drop"]) for item in group),
            "drop_steps": len(group),
        }
        for group in groups
    ]


def _slot_mode(
    rows: list[dict[str, Any]],
    *,
    player_id: int,
    slot: int,
    start: int,
    end: int,
) -> tuple[str, float, int] | None:
    votes: dict[str, float] = {}
    observations: Counter[str] = Counter()
    for row in rows[max(0, start) : min(len(rows), end)]:
        head = row["offline_privileged_hud"][str(player_id)]["hand"][slot]
        value = head.get("value")
        if not head.get("valid") or not isinstance(value, str) or value == "empty":
            continue
        votes[value] = votes.get(value, 0.0) + float(head.get("score", 0.0))
        observations[value] += 1
    if not votes:
        return None
    value, score = max(votes.items(), key=lambda item: item[1])
    return value, float(score), int(observations[value])


def _next_mode(
    rows: list[dict[str, Any]],
    *,
    player_id: int,
    start: int,
    end: int,
) -> tuple[str, float, int] | None:
    votes: dict[str, float] = {}
    observations: Counter[str] = Counter()
    for row in rows[max(0, start) : min(len(rows), end)]:
        head = row["offline_privileged_hud"][str(player_id)]["next_card"]
        value = head.get("value")
        if not head.get("valid") or not isinstance(value, str) or value == "empty":
            continue
        votes[value] = votes.get(value, 0.0) + float(head.get("score", 0.0))
        observations[value] += 1
    if not votes:
        return None
    value, score = max(votes.items(), key=lambda item: item[1])
    return value, float(score), int(observations[value])


def _deck_counts(rows: list[dict[str, Any]], player_id: int) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        for head in row["offline_privileged_hud"][str(player_id)]["hand"]:
            value = head.get("value")
            if head.get("valid") and isinstance(value, str) and value != "empty":
                counts[value] += 1
    return counts


def _marker_observations(
    rows: list[dict[str, Any]], player_id: int
) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        for entity in row["public"]["entities"]:
            normalized = "".join(
                character
                for character in str(entity["visual_class"]).casefold()
                if character.isalnum()
            )
            if normalized != "clock" or entity.get("team_id") != player_id:
                continue
            x1, y1, x2, y2 = entity["sprite_box_normalized"]
            center_x = (float(x1) + float(x2)) * 0.5
            center_y = (float(y1) + float(y2)) * 0.5
            world_x = center_x * 18.0
            source_y = (center_y * 683.0 - 62.0) / 614.0 * 32.0
            if not 0.0 <= world_x <= 18.0 or not 0.0 <= source_y <= 32.0:
                continue
            world_y = 32.0 - source_y
            output.append(
                {
                    "timestamp_ms": int(row["timestamp_ms"]),
                    "confidence": float(entity["confidence"]),
                    "world_position": [world_x, world_y],
                    "tile_absolute": [
                        max(0, min(17, math.floor(world_x))),
                        max(0, min(31, math.floor(world_y))),
                    ],
                }
            )
    return output


def build_labels(
    rows: list[dict[str, Any]],
    vocabulary: Path,
    *,
    use_next_rotation: bool = True,
) -> list[dict[str, Any]]:
    authority = _card_authority(vocabulary)
    labels = []
    for player_id in (0, 1):
        deck_counts = _deck_counts(rows, player_id)
        markers = _marker_observations(rows, player_id)
        last_card_play: dict[str, int] = {}
        for play_index, drop in enumerate(_elixir_drop_groups(rows, player_id)):
            start = int(drop["start_index"])
            end = int(drop["end_index"])
            next_before = _next_mode(
                rows,
                player_id=player_id,
                start=start - 12,
                end=start,
            )
            next_after = _next_mode(
                rows,
                player_id=player_id,
                start=end + 2,
                end=end + 18,
            )
            transitions: list[dict[str, Any]] = []
            for slot in range(4):
                before = _slot_mode(
                    rows,
                    player_id=player_id,
                    slot=slot,
                    start=start - 12,
                    end=start,
                )
                after = _slot_mode(
                    rows,
                    player_id=player_id,
                    slot=slot,
                    start=end + 2,
                    end=end + 18,
                )
                if before is None or after is None or before[0] == after[0]:
                    continue
                card = before[0]
                card_row = authority.get(card)
                cost = None if card_row is None else card_row.get("mana_cost")
                cost_error = (
                    None
                    if not isinstance(cost, int | float)
                    else abs(float(cost) - float(drop["observed_elixir_drop"]))
                )
                transitions.append(
                    {
                        "slot": slot,
                        "card_identity": card,
                        "replacement": after[0],
                        "before_score": before[1],
                        "before_observations": before[2],
                        "after_score": after[1],
                        "after_observations": after[2],
                        "deck_observations": deck_counts[card],
                        "public_cost": cost,
                        "cost_error": cost_error,
                        "cycle_separation": (
                            None
                            if card not in last_card_play
                            else play_index - last_card_play[card]
                        ),
                        "next_before": None if next_before is None else next_before[0],
                        "next_after": None if next_after is None else next_after[0],
                        "next_enters_played_slot": bool(
                            next_before is not None and after[0] == next_before[0]
                        ),
                        "next_advances": bool(
                            next_before is not None
                            and next_after is not None
                            and next_before[0] != next_after[0]
                        ),
                    }
                )
            acceptable: list[dict[str, Any]] = [
                item
                for item in transitions
                if item["deck_observations"] >= 50
                and item["before_observations"] >= 2
                and item["after_observations"] >= 2
                and isinstance(item["cost_error"], float)
                and item["cost_error"] <= 1.0
                and (item["cycle_separation"] is None or item["cycle_separation"] >= 4)
            ]
            next_consistent = [
                item
                for item in acceptable
                if item["next_enters_played_slot"] and item["next_advances"]
            ]
            if use_next_rotation and next_before is not None and next_after is not None:
                acceptable = next_consistent
            acceptable.sort(
                key=lambda item: (
                    float(item["cost_error"]),
                    -int(item["before_observations"]),
                    -float(item["before_score"]),
                )
            )
            identity = acceptable[0] if len(acceptable) == 1 else None
            timestamp = int(drop["timestamp_ms"])
            marker_candidates = [
                marker
                for marker in markers
                if -500 <= marker["timestamp_ms"] - timestamp <= 1_500
            ]
            marker = (
                min(
                    marker_candidates,
                    key=lambda item: (
                        abs(int(item["timestamp_ms"]) - timestamp),
                        -float(item["confidence"]),
                    ),
                )
                if marker_candidates
                else None
            )
            if identity is not None:
                last_card_play[str(identity["card_identity"])] = play_index
            labels.append(
                {
                    "schema": SCHEMA,
                    "label_id": f"p{player_id}-{play_index:04d}",
                    "player_id": player_id,
                    "timestamp_ms": timestamp,
                    "play_valid": True,
                    "play_evidence": "adjacent_public_elixir_drop",
                    "observed_elixir_drop": drop["observed_elixir_drop"],
                    "drop_steps": drop["drop_steps"],
                    "card_identity": (
                        None if identity is None else identity["card_identity"]
                    ),
                    "identity_valid": identity is not None,
                    "identity_evidence": (
                        None
                        if identity is None
                        else (
                            "smoothed_hand_slot_transition_cost_deck_cycle_next_rotation"
                            if identity["next_enters_played_slot"]
                            and identity["next_advances"]
                            else "smoothed_hand_slot_transition_cost_deck_cycle"
                        )
                    ),
                    "identity_candidates": transitions,
                    "deployment_world_position": (
                        None if marker is None else marker["world_position"]
                    ),
                    "deployment_tile_absolute": (
                        None if marker is None else marker["tile_absolute"]
                    ),
                    "placement_valid": marker is not None,
                    "placement_evidence": (
                        None
                        if marker is None
                        else "nearest_same_player_public_deployment_marker"
                    ),
                    "marker_timestamp_ms": (
                        None if marker is None else marker["timestamp_ms"]
                    ),
                    "offline_label_only": True,
                    "next_rotation_evidence": {
                        "before": None if next_before is None else next_before[0],
                        "after": None if next_after is None else next_after[0],
                        "before_observations": (
                            0 if next_before is None else next_before[2]
                        ),
                        "after_observations": 0 if next_after is None else next_after[2],
                        "label_only_future_confirmed": True,
                        "actor_input": False,
                    },
                }
            )
    return sorted(labels, key=lambda row: (row["timestamp_ms"], row["player_id"]))


def evaluate(labels: list[dict[str, Any]], gold_path: Path) -> dict[str, Any]:
    gold_payload = json.loads(gold_path.read_text())
    if gold_payload.get("schema") != GOLD_SCHEMA:
        raise ValueError("unsupported gold schema")
    gold = [row for row in gold_payload["labels"] if row.get("play_valid")]
    used: set[int] = set()
    matches = []
    for prediction in labels:
        candidates = [
            (index, row)
            for index, row in enumerate(gold)
            if index not in used
            and row["player_id"] == prediction["player_id"]
            and abs(int(row["timestamp_ms"]) - int(prediction["timestamp_ms"])) <= 300
        ]
        if not candidates:
            continue
        index, row = min(
            candidates,
            key=lambda item: abs(
                int(item[1]["timestamp_ms"]) - int(prediction["timestamp_ms"])
            ),
        )
        used.add(index)
        matches.append((prediction, row))
    play_tp = len(matches)
    identity_predictions = [row for row in labels if row["identity_valid"]]
    identity_tp = sum(
        prediction["identity_valid"]
        and gold_row.get("identity_valid")
        and prediction["card_identity"] == gold_row.get("card_identity")
        for prediction, gold_row in matches
    )
    identity_gold = sum(bool(row.get("identity_valid")) for row in gold)
    placement_predictions = [row for row in labels if row["placement_valid"]]
    placement_tp = sum(
        prediction["placement_valid"]
        and gold_row.get("placement_valid")
        and prediction["deployment_tile_absolute"]
        == gold_row.get("deployment_tile_absolute")
        for prediction, gold_row in matches
    )
    placement_gold = sum(bool(row.get("placement_valid")) for row in gold)

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    return {
        "gold_labels": len(gold),
        "predicted_plays": len(labels),
        "play_true_positives": play_tp,
        "play_precision": ratio(play_tp, len(labels)),
        "play_recall": ratio(play_tp, len(gold)),
        "identity_predictions": len(identity_predictions),
        "identity_gold": identity_gold,
        "identity_true_positives": identity_tp,
        "identity_precision": ratio(identity_tp, len(identity_predictions)),
        "identity_recall": ratio(identity_tp, identity_gold),
        "placement_predictions": len(placement_predictions),
        "placement_gold": placement_gold,
        "placement_true_positives": placement_tp,
        "placement_precision": ratio(placement_tp, len(placement_predictions)),
        "placement_recall": ratio(placement_tp, placement_gold),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neutral", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gold", type=Path)
    args = parser.parse_args()
    rows = _rows(args.neutral)
    baseline_labels = build_labels(rows, args.vocabulary, use_next_rotation=False)
    labels = build_labels(rows, args.vocabulary, use_next_rotation=True)
    payload = {
        "schema": "clasher.youtube.cached_action_label_manifest.v1",
        "neutral": str(args.neutral.resolve()),
        "neutral_sha256": _sha256(args.neutral),
        "vocabulary": str(args.vocabulary.resolve()),
        "vocabulary_sha256": _sha256(args.vocabulary),
        "counts": {
            "plays": len(labels),
            "identities": sum(row["identity_valid"] for row in labels),
            "placements": sum(row["placement_valid"] for row in labels),
            "complete_actions": sum(
                row["identity_valid"] and row["placement_valid"] for row in labels
            ),
            "by_player": dict(Counter(str(row["player_id"]) for row in labels)),
        },
        "next_rotation_increment": {
            "baseline_identities_without_next_constraint": sum(
                row["identity_valid"] for row in baseline_labels
            ),
            "identities_with_next_constraint": sum(
                row["identity_valid"] for row in labels
            ),
            "baseline_complete_actions_without_next_constraint": sum(
                row["identity_valid"] and row["placement_valid"]
                for row in baseline_labels
            ),
            "complete_actions_with_next_constraint": sum(
                row["identity_valid"] and row["placement_valid"] for row in labels
            ),
            "contract": (
                "both spectator Next labels are offline extraction evidence only; each actor "
                "projection may expose only its own current-frame Next"
            ),
        },
        "labels": labels,
        "gold_evaluation": (
            None if args.gold is None else evaluate(labels, args.gold.resolve())
        ),
        "offline_label_only": True,
    }
    _atomic_json(args.output, payload)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": _sha256(args.output),
                "counts": payload["counts"],
                "gold_evaluation": payload["gold_evaluation"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
