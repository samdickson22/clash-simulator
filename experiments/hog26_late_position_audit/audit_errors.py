"""Retrospective error decomposition; endpoint membership is never a feature."""

import json
from pathlib import Path

import numpy as np
from audit_positions import sha


def main():
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_late_representative_error_decomposition_20260912.json"
    if output.exists():
        raise ValueError("preserve existing error decomposition")
    position_path = root / "reports/hog26_late_representative_position_audit_20260912.json"
    positions = json.loads(position_path.read_text())
    manifest_path = root / "reports/hog26_scaling_globals_comparison_20260912/fitting_manifest.json"
    if sha(manifest_path) != positions["manifest_sha256"]:
        raise ValueError("position audit manifest differs")
    manifest = json.loads(manifest_path.read_text())
    rows = {item["game"]: item for item in positions["late_games"]}
    offsets, current, target, last = [], [], [], []
    offset = 0
    for game, record in enumerate(manifest["input_games"]):
        if sha(record["path"]) != record["sha256"]:
            raise ValueError("training archive changed")
        with np.load(record["path"], allow_pickle=False) as archive:
            g = archive["global_features"]
            if game in rows:
                row = rows[game]["representative_row"]
                offsets.append(offset + row)
                current.append(float((g[row, 8:11].sum() - g[row, 11:14].sum()) / 3))
                target.append(float(archive["terminal_tower_margin"]))
                last.append(rows[game]["last_row"])
        offset += len(g)
    current, target, last = np.asarray(current), np.asarray(target), np.asarray(last)
    resources = {str(position_path): sha(position_path), str(manifest_path): sha(manifest_path)}
    models = {}
    for model, directory, seeds in (
            ("tree", "hog26_scaling_tree_comparison_20260912", (1279501,)),
            ("numeric", "hog26_residual_margin_comparison_20260912", (1279501, 1279502)),
            ("semantic", "hog26_semantic_margin_comparison_20260912", (1279501, 1279502))):
        for seed in seeds:
            path = root / "reports" / directory / f"seed{seed}-oof.npz"
            resources[str(path)] = sha(path)
            with np.load(path, allow_pickle=False) as saved:
                prediction = saved["margin"][offsets]
            groups = {}
            for name, mask in (("last_decision", last), ("earlier_decision", ~last)):
                baseline_error = np.abs(target[mask] - current[mask])
                error = np.abs(target[mask] - prediction[mask])
                groups[name] = {"games": int(mask.sum()),
                                "baseline_mae": float(baseline_error.mean()),
                                "model_mae": float(error.mean()),
                                "margin_gain": float((baseline_error - error).mean()),
                                "mean_absolute_correction": float(np.abs(prediction[mask] - current[mask]).mean()),
                                "median_absolute_correction": float(np.median(np.abs(prediction[mask] - current[mask])))}
            models[f"{model}-seed{seed}"] = groups
    report = {"scope": "Post hoc OOF error decomposition on the 80 existing training late representatives.",
              "terminal_membership_analysis_only": True, "fitting": False, "acceptance": False,
              "models": models, "resources": resources, "source_sha256": sha(__file__),
              "limitations": ["Retrospective groups cannot be selected by the model using future terminal metadata.",
                              "Subgroup point estimates are descriptive, not new acceptance tests or causal evidence."]}
    with output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(models), flush=True)


if __name__ == "__main__":
    main()
