"""Actual next-decision termination is a supervised target, never an input."""

import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_labels(records):
    labels = []
    for record in records:
        if sha(record["path"]) != record["sha256"]:
            raise ValueError("auxiliary archive changed")
        with np.load(record["path"], allow_pickle=False) as archive:
            ticks = archive["tick"]
            terminal = int(archive["terminal_tick"])
            interval = int(archive["decision_interval_ticks"])
            actual = bool(archive["actual_terminal"])
        if (not actual or ticks.ndim != 1 or not len(ticks) or interval <= 0
                or not (np.diff(ticks) > 0).all() or terminal <= ticks[-1]
                or terminal - ticks[-1] > interval
                or (len(ticks) > 1 and terminal - ticks[-2] <= interval)):
            raise ValueError("next-decision termination label is ambiguous")
        target = np.zeros(len(ticks), dtype=np.float32)
        target[-1] = 1
        labels.append(target)
    result = np.concatenate(labels)
    if result.shape != (618149,) or result.sum() != 1536:
        raise ValueError("auxiliary target inventory differs")
    return result


def main():
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_terminal_auxiliary_label_audit_20260912.json"
    if output.exists():
        raise ValueError("preserve existing label audit")
    manifest_path = root / "reports/hog26_scaling_globals_comparison_20260912/fitting_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    labels = load_labels(manifest["input_games"])
    report = {"status": "passed-actual-next-decision-label-audit", "games": 1536,
              "rows": len(labels), "positive_rows": int(labels.sum()),
              "definition": "The actual terminal tick occurs after this predecision row and within its decision interval.",
              "each_game_one_positive": True, "labels_sha256": hashlib.sha256(labels.tobytes()).hexdigest(),
              "manifest_sha256": sha(manifest_path), "source_sha256": sha(__file__),
              "input_changes": False, "outcome_fitting": False, "acceptance": False,
              "limitation": "Termination depends on the frozen behavior policy after observation; this is not an action-independent hazard or an outcome-model acceptance test."}
    with output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
