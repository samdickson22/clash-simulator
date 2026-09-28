"""Describe corrected training diagnostics without opening evaluation corpora."""

import json
from pathlib import Path

import numpy as np

from clasher.rl.direct_simple_behavior import load_direct_simple_behavior_corpus
from scripts.collect_hog26_direct_simple_behavior import file_sha256
from scripts.hog26_scenario_clusters import corpus_matchup_clusters


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / "reports/hog26_corrected_hybrid_margin_screen_20260909.json"
    report = json.loads(source.read_text())
    representatives = np.asarray(report["representative_rows"])
    targets, currents, phases, clusters, families = [], [], [], [], []
    episode_cursor = 0
    for spec in report["source_corpora"]:
        path = root / spec["path"]
        if file_sha256(path) != spec["sha256"]:
            raise ValueError("source corpus changed")
        metadata, corpus = load_direct_simple_behavior_corpus(path)
        public = corpus.arrays["global_features"]
        lengths = np.diff(corpus.episode_offsets)
        targets.append(corpus.arrays["terminal_tower_margins"].copy())
        currents.append((public[:, 8:11].sum(1) - public[:, 11:14].sum(1)) / 3)
        phases.append(np.minimum((public[:, 0] * 3).astype(int), 2))
        clusters.extend(np.repeat(corpus_matchup_clusters(metadata, corpus), lengths))
        end = episode_cursor + corpus.episode_count
        families.extend(np.repeat(report["source_episode_families"][episode_cursor:end], lengths))
        episode_cursor = end
        del corpus
    target = np.concatenate(targets)[representatives]
    current = np.concatenate(currents)[representatives]
    phase = np.concatenate(phases)[representatives]
    cluster = np.asarray(clusters)[representatives]
    family = np.asarray(families)[representatives]

    def interval(gain, groups):
        unique, inverse = np.unique(groups, return_inverse=True)
        sums = np.bincount(inverse, weights=gain)
        counts = np.bincount(inverse)
        rng = np.random.default_rng(1278971)
        sampled = rng.integers(len(unique), size=(2000, len(unique)))
        means = sums[sampled].sum(1) / counts[sampled].sum(1)
        lo, hi = np.quantile(means, [0.025, 0.975])
        return {"point": float(gain.mean()), "lower_95": float(lo),
                "upper_95": float(hi), "clusters": len(unique), "replicates": 2000}

    results = []
    for result in report["results"]:
        gain = np.abs(current - target) - np.abs(np.asarray(result["predictions"]) - target)
        uncertainty = {}
        for name, selected in [("overall", np.ones(len(phase), dtype=bool))] + [
            (name, phase == index) for index, name in enumerate(("early", "middle", "late"))
        ]:
            uncertainty[name] = {
                "paired_scenario": interval(gain[selected], cluster[selected]),
                "training_family": interval(gain[selected], family[selected]),
            }
        results.append({"seed": result["seed"], "uncertainty": uncertainty,
                        "pooled": result["pooled"],
                        "folds": [{"families": f["held_out_families"],
                                   "out_of_fold": f["out_of_fold"],
                                   "full_phase": f["full_phase_out_of_fold"]}
                                  for f in result["folds"]]})
    destination = root / "reports/hog26_corrected_margin_reassessment_20260909.json"
    with destination.open("x") as stream:
        json.dump({"status": "candidate design remains under review",
                   "scope": "Training-only diagnostic. Bootstrap describes fixed out-of-fold predictions; it does not refit models or establish independent acceptance. Family estimates have only eight clusters.",
                   "source_report": str(source.relative_to(root)),
                   "source_sha256": file_sha256(source),
                   "script_sha256": file_sha256(Path(__file__)),
                   "bootstrap_seed": 1278971, "results": results}, stream, indent=2)
        stream.write("\n")
    for result in results:
        print(json.dumps({"seed": result["seed"], "uncertainty": result["uncertainty"]}))


if __name__ == "__main__":
    main()
