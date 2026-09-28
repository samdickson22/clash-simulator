from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from scripts.extract_tv_royale_youtube_fullmatch import _atomic_json, _sha256


def _jsonl(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _head(row: dict[str, Any], player_id: int, slot: int | str) -> dict[str, Any]:
    hud = row["offline_privileged_hud"][str(player_id)]
    return cast(
        dict[str, Any],
        hud["next_card"] if slot == "next" else hud["hand"][int(slot)],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neutral", type=Path, required=True)
    parser.add_argument("--transients", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--mask-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    neutral = _jsonl(args.neutral)
    transients = _jsonl(args.transients)
    gold = json.loads(args.gold.read_text())
    by_time = {int(row["timestamp_ms"]): row for row in neutral}
    transient_by_time = {int(row["timestamp_ms"]): row for row in transients}
    checks = []
    field_counts: dict[str, Counter[str]] = {}
    for expected in gold["records"]:
        timestamp = int(expected["timestamp_ms"])
        player_id = int(expected["player_id"])
        slot = expected["slot"]
        head = _head(by_time[timestamp], player_id, slot)
        semantics = head["visual_semantics"]
        actual = {
            "variant_value": semantics["variant_visual_state"]["value"],
            "variant_candidate": semantics["variant_visual_state"]["candidate"],
            "variant_valid": semantics["variant_visual_state"]["valid"],
            "evolution_ready": semantics["evolution_ready"]["value"],
            "evolution_ready_valid": semantics["evolution_ready"]["valid"],
            "progress_diamonds": semantics["evolution_progress_diamonds"]["value"],
            "progress_diamonds_valid": semantics["evolution_progress_diamonds"][
                "valid"
            ],
            "disabled": semantics["disabled_visual"]["value"],
            "disabled_valid": semantics["disabled_visual"]["valid"],
            "printed_cost": semantics["printed_cost"].get("value"),
            "printed_cost_valid": semantics["printed_cost"].get("valid", False),
        }
        transient_slot = 4 if slot == "next" else int(slot)
        actual["selected_or_disappearing"] = transient_by_time[timestamp]["players"][
            str(player_id)
        ][transient_slot]["selected_or_disappearing_candidate"]
        expected_fields = {
            key: value
            for key, value in expected.items()
            if key
            not in {
                "timestamp_ms",
                "player_id",
                "slot",
            }
        }
        field_results = {}
        for key, value in expected_fields.items():
            validity_key = {
                "evolution_ready": "evolution_ready_valid",
                "progress_diamonds": "progress_diamonds_valid",
                "disabled": "disabled_valid",
                "printed_cost": "printed_cost_valid",
            }.get(key)
            missing = bool(validity_key is not None and not actual[validity_key])
            if key == "variant_value" and not actual["variant_valid"]:
                missing = True
            if key == "variant_valid":
                status = "correct" if actual[key] == value else "missing"
            elif missing:
                status = "missing"
            else:
                status = "correct" if actual[key] == value else "wrong"
            field_results[key] = status
            field_counts.setdefault(key, Counter())[status] += 1
            field_counts[key]["gold"] += 1
        checks.append(
            {
                "timestamp_ms": timestamp,
                "player_id": player_id,
                "slot": slot,
                "expected": expected,
                "actual": actual,
                "field_results": field_results,
                "passed": all(value != "wrong" for value in field_results.values()),
            }
        )

    mask_manifest = json.loads(args.mask_manifest.read_text())
    actor_privacy = []
    for artifact in mask_manifest["artifacts"]["actor_trajectories"]:
        actor_id = int(artifact["actor_id"])
        rows = _jsonl(Path(artifact["path"]))
        bad = 0
        next_missing = 0
        for row in rows:
            serialized = json.dumps(row, sort_keys=True)
            bad += int(
                any(
                    token in serialized
                    for token in (
                        "offline_hud_transient",
                        "offline_privileged_hud",
                        "family_scores",
                        "expert_action",
                        "label_only_future_confirmed",
                    )
                )
            )
            next_missing += int(
                "visual_semantics" not in row["own_hud"]["next_card"]
            )
        actor_privacy.append(
            {
                "actor_id": actor_id,
                "rows": len(rows),
                "forbidden_field_rows": bad,
                "own_next_semantics_missing_rows": next_missing,
                "passed": bad == 0 and next_missing == 0,
            }
        )
    failed = [check for check in checks if not check["passed"]]
    metrics = {}
    for field, counts in sorted(field_counts.items()):
        predicted = counts["correct"] + counts["wrong"]
        metrics[field] = {
            "gold": counts["gold"],
            "predicted": predicted,
            "correct": counts["correct"],
            "wrong": counts["wrong"],
            "missing": counts["missing"],
            "precision": counts["correct"] / predicted if predicted else None,
            "coverage": predicted / counts["gold"] if counts["gold"] else None,
        }
    status = "passed" if not failed and all(row["passed"] for row in actor_privacy) else "failed"
    report = {
        "schema": "clasher.youtube.hud_semantics_verifier.v1",
        "status": status,
        "neutral_sha256": _sha256(args.neutral),
        "transients_sha256": _sha256(args.transients),
        "gold_sha256": _sha256(args.gold),
        "mask_manifest_sha256": _sha256(args.mask_manifest),
        "gold_records": len(checks),
        "passed_records": len(checks) - len(failed),
        "failed_records": len(failed),
        "checks": checks,
        "head_metrics": metrics,
        "actor_privacy": actor_privacy,
        "promotion_gate": "blocked_pending_replay_disjoint_and_exact_variant_art",
    }
    _atomic_json(args.output, report)
    print(json.dumps({"output": str(args.output), "sha256": _sha256(args.output), "status": status, "gold_records": len(checks), "failed_records": len(failed), "actor_privacy": actor_privacy}, indent=2))
    if status != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
