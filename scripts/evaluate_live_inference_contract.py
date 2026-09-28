"""Score model-owned live inference trajectories against held-out labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from clasher.rl.live_inference_contract import (
    EvaluationThresholds,
    evaluate_predictions,
    file_sha256,
    load_jsonl,
    parse_evaluation_labels,
    parse_model_prediction,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--minimum-samples-per-metric", type=int, default=1)
    parser.add_argument("--maximum-clock-mae-seconds", type=float, default=1.0)
    parser.add_argument("--maximum-elixir-mae", type=float, default=0.5)
    parser.add_argument("--minimum-cycle-accuracy", type=float, default=0.95)
    parser.add_argument("--minimum-placement-within-one-tile", type=float, default=0.90)
    parser.add_argument("--maximum-hp-mae", type=float, default=0.10)
    parser.add_argument("--minimum-status-f1", type=float, default=0.90)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prediction_path = Path(args.predictions).expanduser().resolve()
    label_path = Path(args.labels).expanduser().resolve()
    thresholds = EvaluationThresholds(
        minimum_samples_per_metric=args.minimum_samples_per_metric,
        maximum_clock_mae_seconds=args.maximum_clock_mae_seconds,
        maximum_elixir_mae=args.maximum_elixir_mae,
        minimum_cycle_accuracy=args.minimum_cycle_accuracy,
        minimum_placement_within_one_tile=args.minimum_placement_within_one_tile,
        maximum_hp_mae=args.maximum_hp_mae,
        minimum_status_f1=args.minimum_status_f1,
    )
    report = evaluate_predictions(
        load_jsonl(prediction_path, parse_model_prediction),
        load_jsonl(label_path, parse_evaluation_labels),
        thresholds=thresholds,
    )
    report["sources"] = {
        "predictions": str(prediction_path),
        "predictions_sha256": file_sha256(prediction_path),
        "labels": str(label_path),
        "labels_sha256": file_sha256(label_path),
    }
    output = Path(args.report_out).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "metrics": report["metrics"]}, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
