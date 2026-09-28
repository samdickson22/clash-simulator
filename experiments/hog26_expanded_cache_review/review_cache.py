"""Independent cache metadata, public-baseline and coverage review before model plans."""

import json
from pathlib import Path

import numpy as np
import torch
from cache_reader import read_complete_cache
from expanded_authority import load_authority
from scalar_evaluation import EvaluationIndex, coverage, evaluation_weights, slice_masks
from terminal_labels import sha


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_expanded_cache_review_20260913.json"
    if output.exists():
        raise ValueError("preserve existing expanded cache review")
    authority = load_authority(root)
    directory = root / "reports/hog26_expanded_feature_cache_20260913"
    mapped, evaluation, complete, cluster_names = read_complete_cache(directory)
    records = complete["game_records"]
    for game, record in zip(authority.games, records, strict=True):
        expected = {"path": str(game.path), "sha256": game.sha256, "cohort": game.cohort,
                    "rows": game.record["rows"], "label": 2 - int(np.argmax(game.record["outcome_wdl"])),
                    "terminal_margin": game.record["terminal_tower_margin"],
                    "family": game.metadata["family_id"], "style": game.metadata["style"],
                    "seat": game.metadata["learner_seat"], "cluster": game.metadata["cluster_id"]}
        if record != expected:
            raise ValueError("cached game labels or metadata differ from audited collection records")
    ids, progress, labels, target, current, seats, styles, folds, clusters, families = evaluation
    names = complete["feature_names"]
    hp_columns = [names.index(f"global{i}") for i in range(8, 14)]
    confidence_columns = [names.index(f"global{i}.confidence") for i in range(8, 14)]
    progress_column, progress_confidence = names.index("global0"), names.index("global0.confidence")
    for start in range(0, len(progress), 8192):
        end = min(start + 8192, len(progress))
        block = np.array(mapped[start:end], copy=True)
        if not np.all(block[:, confidence_columns] == 1) or not np.all(block[:, progress_confidence] == 1):
            raise ValueError("cached public progress or tower health is unavailable")
        hp = np.ascontiguousarray(block[:, hp_columns])
        baseline = (hp[:, :3].sum(1) - hp[:, 3:].sum(1)) / 3
        if not np.array_equal(baseline, current[start:end]) or not np.array_equal(block[:, progress_column], progress[start:end]):
            raise ValueError("row metadata differs from the actual public feature columns")
    mapped._mmap.close()
    index = EvaluationIndex(ids, progress)
    masks = slice_masks(progress, seats, styles, folds)
    masks.update({f"family/{family}": families == family for family in np.unique(families)})
    distributions = {}
    for representative, name in ((False, "all_states"), (True, "representatives")):
        distributions[name] = {}
        for key, mask in masks.items():
            weights = evaluation_weights(ids, progress, mask, representative=representative, index=index)
            distributions[name][key] = coverage(ids, labels, clusters, weights)
    if len(cluster_names) != 3072 or len(np.unique(ids)) != 6144:
        raise ValueError("expanded review game or cluster counts differ")
    report = {"status": "complete-expanded-cache-review", "games": 6144, "rows": len(ids), "clusters": 3072,
              "cache_complete_sha256": sha(directory / "complete.json"), "feature_sha256": complete["cache"]["sha256"],
              "label_and_game_metadata_exact": True, "public_progress_and_baseline_exact": True,
              "outcome_counts": complete["outcome_counts"], "coverage": distributions,
              "source_sha256": sha(__file__), "fitting_allowed": False, "acceptance": False,
              "scope": "Complete data and cache review only. Model-specific source and actual training-memory readiness remain required."}
    with output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "games": 6144, "rows": len(ids),
                      "outcomes": complete["outcome_counts"], "late": distributions["representatives"]["phase/late"]}), flush=True)


if __name__ == "__main__":
    main()
