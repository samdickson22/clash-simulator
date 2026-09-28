from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2

from clasher.rl.tv_royale_replay import TVRoyalePlacementConverter
from scripts.extract_tv_royale_youtube_fullmatch import (
    HudRecognizer,
    StableIdentityResolver,
    _atomic_json,
)

SCHEMA = "clasher.youtube.hud_identity_backend_evaluation.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize(
    records: list[dict[str, Any]], decisions: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(records) != len(decisions):
        raise ValueError("record and decision counts differ")
    counts: Counter[str] = Counter()
    events: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(
        list
    )
    for record, decision in zip(records, decisions, strict=True):
        gold = record["card_identity"]
        counts["rows"] += 1
        counts["candidate_correct"] += decision["candidate"] == gold
        counts["valid"] += bool(decision["valid"])
        counts["valid_correct"] += bool(
            decision["valid"] and decision["value"] == gold
        )
        events[str(record["label_id"])].append((record, decision))
    for items in events.values():
        gold = items[0][0]["card_identity"]
        candidate_values = [item[1]["candidate"] for item in items]
        candidates = Counter(candidate_values)
        counts["event_candidate_correct"] += candidates.most_common(1)[0][0] == gold
        unanimous_candidate = (
            candidate_values[0] if len(set(candidate_values)) == 1 else None
        )
        counts["event_candidate_unanimous"] += unanimous_candidate is not None
        counts["event_candidate_unanimous_correct"] += unanimous_candidate == gold
        valid = Counter(
            item[1]["value"] for item in items if bool(item[1]["valid"])
        )
        counts["event_valid"] += bool(valid)
        counts["event_valid_correct"] += bool(
            valid and valid.most_common(1)[0][0] == gold
        )

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    return {
        **dict(counts),
        "events": len(events),
        "row_candidate_accuracy": ratio(counts["candidate_correct"], counts["rows"]),
        "row_valid_precision": ratio(counts["valid_correct"], counts["valid"]),
        "row_valid_recall": ratio(counts["valid_correct"], counts["rows"]),
        "event_candidate_accuracy": ratio(
            counts["event_candidate_correct"], len(events)
        ),
        "event_candidate_unanimous_precision": ratio(
            counts["event_candidate_unanimous_correct"],
            counts["event_candidate_unanimous"],
        ),
        "event_candidate_unanimous_recall": ratio(
            counts["event_candidate_unanimous_correct"], len(events)
        ),
        "event_valid_precision": ratio(
            counts["event_valid_correct"], counts["event_valid"]
        ),
        "event_valid_recall": ratio(counts["event_valid_correct"], len(events)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--template-root", type=Path, required=True)
    parser.add_argument("--card-weight", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    holdout_path = args.holdout.resolve()
    holdout = json.loads(holdout_path.read_text(encoding="utf-8"))
    root = holdout_path.parent
    records = list(holdout["records"])
    crops = []
    for record in records:
        crop = cv2.imread(str(root / record["path"]), cv2.IMREAD_COLOR)
        if crop is None:
            raise ValueError(f"could not read {record['path']}")
        crops.append(crop)
    resolver = StableIdentityResolver(
        args.vocabulary.resolve(), TVRoyalePlacementConverter(source_frame_hz=10)
    )
    evaluations: dict[str, Any] = {}
    raw_decisions: dict[str, list[dict[str, Any]]] = {}
    for backend in ("pil", "pil-batched", "tensor"):
        recognizer = HudRecognizer(
            args.template_root.resolve(),
            resolver,
            device=args.device,
            card_weight_path=args.card_weight.resolve(),
            card_preprocess_backend=backend,
        )
        decisions = recognizer.cards(crops)
        raw_decisions[backend] = decisions
        evaluations[backend] = summarize(records, decisions)

    pil_exact = raw_decisions["pil"] == raw_decisions["pil-batched"]
    tensor = evaluations["tensor"]
    gates = {
        "pil_batched_exact_to_pil": pil_exact,
        "tensor_candidate_accuracy_one": tensor["row_candidate_accuracy"] == 1.0,
        "tensor_event_valid_precision_one": tensor["event_valid_precision"] == 1.0,
        "tensor_event_valid_recall_one": tensor["event_valid_recall"] == 1.0,
        "tensor_offline_unanimous_precision_one": (
            tensor["event_candidate_unanimous_precision"] == 1.0
        ),
        "tensor_offline_unanimous_recall_one": (
            tensor["event_candidate_unanimous_recall"] == 1.0
        ),
    }
    live_gates = {
        key: value
        for key, value in gates.items()
        if not key.startswith("tensor_offline_unanimous")
    }
    offline_gates = {
        "pil_batched_exact_to_pil": gates["pil_batched_exact_to_pil"],
        "tensor_candidate_accuracy_one": gates["tensor_candidate_accuracy_one"],
        "tensor_offline_unanimous_precision_one": gates[
            "tensor_offline_unanimous_precision_one"
        ],
        "tensor_offline_unanimous_recall_one": gates[
            "tensor_offline_unanimous_recall_one"
        ],
    }
    status = (
        "passed_live_single_frame"
        if all(live_gates.values())
        else "passed_offline_temporal"
        if all(offline_gates.values())
        else "failed"
    )
    payload = {
        "schema": SCHEMA,
        "status": status,
        "holdout": str(holdout_path),
        "holdout_sha256": _sha256(holdout_path),
        "vocabulary_sha256": _sha256(args.vocabulary.resolve()),
        "card_weight_sha256": _sha256(args.card_weight.resolve()),
        "device": args.device,
        "evaluations": evaluations,
        "gates": gates,
        "gate_groups": {"live_single_frame": live_gates, "offline_temporal": offline_gates},
        "limitations": [
            "All real crops come from one replay and are held out together.",
            "The set covers only uniquely transitioned, manually identified plays.",
            "Promotion requires the same gates on untouched replay-disjoint videos.",
        ],
    }
    _atomic_json(args.output.resolve(), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
