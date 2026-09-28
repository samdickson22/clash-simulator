"""Explain late representative selection using terminal metadata only for audit."""

import hashlib
import json
from pathlib import Path

import numpy as np
from scalar_evaluation import EvaluationIndex, evaluation_weights


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_late_representative_position_audit_20260912.json"
    if output.exists():
        raise ValueError("preserve existing position audit")
    manifest_path = root / "reports/hog26_scaling_globals_comparison_20260912/fitting_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    blocks = []
    late_games = []
    for game, record in enumerate(manifest["input_games"]):
        path = Path(record["path"])
        if sha(path) != record["sha256"]:
            raise ValueError("training archive changed")
        with np.load(path, allow_pickle=False) as archive:
            globals_ = archive["global_features"]
            progress = globals_[:, 0]
            current = (globals_[:, 8:11].sum(1) - globals_[:, 11:14].sum(1)) / 3
            terminal = float(archive["terminal_tower_margin"])
            tick = archive["tick"]
            end_tick = int(archive["terminal_tick"])
            interval = int(archive["decision_interval_ticks"])
        ids = np.full(len(progress), game)
        index = EvaluationIndex(ids, progress)
        rep = index.representative_mask
        late = progress >= 2 / 3
        if late.any():
            selected = np.flatnonzero(rep & late)
            if len(selected) != 1:
                raise ValueError("late representative count differs")
            row = int(selected[0])
            late_games.append({"game": game, "archive": str(path), "rows": len(progress),
                               "representative_row": row, "last_row": row == len(progress) - 1,
                               "progress": float(progress[row]),
                               "decision_intervals_to_terminal": float((end_tick - tick[row]) / interval),
                               "baseline_error": abs(terminal - float(current[row]))})
        blocks.append((ids, progress, current, np.full(len(progress), terminal),
                       (end_tick - tick) / interval, np.arange(len(progress)) == len(progress) - 1))
    ids, progress, current, terminal, remaining, last = [np.concatenate([b[i] for b in blocks]) for i in range(6)]
    index = EvaluationIndex(ids, progress)
    if len(ids) != 618149 or len(late_games) != 80:
        raise ValueError("training position counts differ")
    summaries = {}
    for representative, name in ((False, "all_states"), (True, "representatives")):
        weights = evaluation_weights(ids, progress, index.phases == 2, representative=representative, index=index)
        summaries[name] = {"rows": int((weights > 0).sum()),
                           "baseline_mae": float(np.sum(np.abs(terminal - current) * weights)),
                           "last_decision_weight": float(weights[last].sum()),
                           "within_one_interval_weight": float(weights[remaining <= 1].sum()),
                           "within_five_intervals_weight": float(weights[remaining <= 5].sum())}
    reference_path = root / "reports/hog26_semantic_margin_comparison_20260912/seed1279501-summary.json"
    reference = json.loads(reference_path.read_text())
    for name, summary in summaries.items():
        if not np.isclose(summary["baseline_mae"], reference[name]["phase/late"]["metrics"]["baseline_margin_mae"], rtol=1e-12, atol=1e-12):
            raise ValueError("baseline MAE does not reproduce fixed report")
    report = {"scope": "Read-only explanation of representative late positions in the existing training corpus.",
              "terminal_metadata_is_analysis_only": True, "model_input_changes": False,
              "fitting": False, "acceptance": False, "late_games": late_games,
              "summary": summaries, "manifest_sha256": sha(manifest_path),
              "reference_sha256": sha(reference_path), "source_sha256": sha(__file__),
              "limitation": "Endpoint proximity is known retrospectively in this audit; it is not available to the model or a reason to change the frozen metric."}
    with output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(summaries), flush=True)


if __name__ == "__main__":
    main()
