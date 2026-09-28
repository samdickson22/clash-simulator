"""Select a cross-seed-safe mechanics slot candidate without test-set peeking."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from pathlib import Path
from typing import Any


def _selected_arm(
    *,
    name: str,
    sweep: dict[str, Any],
    finetune_reports: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if sweep.get("schema") != "mechanics-slot-normalized-blend-sweep-v1":
        raise ValueError(f"{name} has an unsupported sweep schema")
    probes = list(sweep.get("per_probe") or ())
    if len(probes) != 3:
        raise ValueError(f"{name} must contain exactly three probe seeds")
    paths = [str(probe.get("probe", "")) for probe in probes]
    if any(not path for path in paths) or len(set(paths)) != 3:
        raise ValueError(f"{name} probe paths must be present and unique")
    selected = sweep.get("selected")
    if selected is None:
        return {
            "name": name,
            "eligible": False,
            "reason": "no_cross_seed_safe_alpha",
        }
    alpha = float(selected["alpha"])
    aggregate = [
        row
        for row in sweep.get("aggregate_rows", ())
        if float(row["alpha"]) == alpha
    ]
    if len(aggregate) != 1 or not bool(aggregate[0].get("accepted")):
        raise ValueError(f"{name} selected alpha is not an accepted aggregate row")
    if aggregate[0] != selected:
        raise ValueError(f"{name} selected row does not match its aggregate row")
    if finetune_reports is not None:
        if len(finetune_reports) != 3:
            raise ValueError("fine-tuned arm requires exactly three seed reports")
        sources = [str(report.get("source_probe", "")) for report in finetune_reports]
        if len(set(sources)) != 3 or any(not source for source in sources):
            raise ValueError("fine-tuned source probes must be present and unique")
        if not all(bool(report.get("promoted")) for report in finetune_reports):
            return {
                "name": name,
                "eligible": False,
                "reason": "not_all_finetune_seeds_promoted",
            }
        validation_modes = {
            str((report.get("human_validation_source") or {}).get("mode", ""))
            for report in finetune_reports
        }
        if validation_modes != {"external_replay_disjoint"}:
            raise ValueError("fine-tuned reports require external replay validation")

    seed_rows: list[dict[str, Any]] = []
    for probe in probes:
        matches = [
            row for row in probe.get("rows", ()) if float(row["alpha"]) == alpha
        ]
        if len(matches) != 1:
            raise ValueError(f"{name} probe is missing the selected alpha")
        row = matches[0]
        seed_rows.append(
            {
                "probe": str(probe["probe"]),
                "human_accuracy": float(row["human"]["accuracy"]),
                "human_base_accuracy": float(row["human"]["base_accuracy"]),
                "validation_disagreement": float(
                    row["validation"]["disagreement_with_base"]
                ),
                "heldout_disagreement": float(
                    row["heldout"]["disagreement_with_base"]
                ),
            }
        )
    median_seed = sorted(
        seed_rows,
        key=lambda row: (row["human_accuracy"], row["probe"]),
    )[1]
    return {
        "name": name,
        "eligible": True,
        "alpha": alpha,
        "base_scale": 1.0 - alpha,
        "query_scale": alpha,
        "human_accuracy_mean": float(selected["human_accuracy_mean"]),
        "human_accuracy_min": float(selected["human_accuracy_min"]),
        "validation_disagreement_max": float(
            selected["validation_disagreement_max"]
        ),
        "heldout_disagreement_max": float(selected["heldout_disagreement_max"]),
        "median_seed": median_seed,
        "seed_rows": seed_rows,
    }


def select_candidate(
    *,
    zero_shot_sweep: dict[str, Any],
    finetuned_sweep: dict[str, Any],
    finetune_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    arms = [
        _selected_arm(
            name="zero_shot",
            sweep=zero_shot_sweep,
            finetune_reports=None,
        ),
        _selected_arm(
            name="human_finetuned",
            sweep=finetuned_sweep,
            finetune_reports=finetune_reports,
        ),
    ]
    eligible = [arm for arm in arms if arm["eligible"]]
    selected = (
        max(
            eligible,
            key=lambda arm: (
                arm["human_accuracy_mean"],
                arm["name"] == "zero_shot",
                -arm["alpha"],
            ),
        )
        if eligible
        else None
    )
    return {
        "schema": "mechanics-slot-cross-seed-selection-v1",
        "selection_data": "human_validation_only",
        "heldout_archetype_used_for_selection": False,
        "chronology_used_for_selection": False,
        "seed_policy": "median_validation_seed_not_best_seed",
        "status": "candidate_selected" if selected is not None else "rejected",
        "selected": selected,
        "arms": arms,
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zero-shot-sweep", required=True, type=Path)
    parser.add_argument("--finetuned-sweep", required=True, type=Path)
    parser.add_argument(
        "--finetune-report",
        action="append",
        required=True,
        type=Path,
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    decision = select_candidate(
        zero_shot_sweep=_load_json(args.zero_shot_sweep),
        finetuned_sweep=_load_json(args.finetuned_sweep),
        finetune_reports=[_load_json(path) for path in args.finetune_report],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n")
    print(json.dumps(decision, sort_keys=True))


if __name__ == "__main__":
    main()
