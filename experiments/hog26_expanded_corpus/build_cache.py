"""Audit every full game and stream the unchanged actor-visible feature matrix."""

import hashlib
import json
import resource
import shutil
import sys
from pathlib import Path

import numpy as np
import torch
from body_features import augmented_features, feature_names
from body_stats import compile_body_table
from cache_contract import game_inventory_hash, load_plan, sources
from expanded_authority import load_authority, read_game
from feature_store import FeatureStore
from residual_features import make_layout
from semantic_contract import load_plan as load_feature_plan
from terminal_labels import sha


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    plan_path = root / "reports/hog26_expanded_feature_plan_20260913.json"
    plan = load_plan(plan_path)
    authority = load_authority(root)
    if (game_inventory_hash(authority.games) != plan.game_inventory_sha256
            or authority.cohort_rows != plan.cohort_rows):
        raise ValueError("expanded cache inventory differs from frozen extraction plan")
    output = root / "reports/hog26_expanded_feature_cache_20260913"
    if output.exists():
        raise ValueError("preserve existing expanded cache output")
    if shutil.disk_usage(root).free < plan.rows * plan.columns * 4 + 2 * 1024**3:
        raise ValueError("insufficient free space for the exact expanded cache")
    feature_plan = load_feature_plan(plan.feature_plan)
    if authority.vocabulary != feature_plan.data.vocabulary:
        raise ValueError("expanded cache vocabulary differs")
    table = compile_body_table(authority.vocabulary)
    layout = make_layout(len(authority.vocabulary), feature_plan.data.hand_tokens)
    output.mkdir()
    store = FeatureStore(output / "features.f32", plan.rows, plan.columns)
    progress = np.empty(plan.rows, dtype=np.float32)
    current = np.empty(plan.rows, dtype=np.float32)
    selected = np.random.default_rng(1280201).integers(0, plan.rows, size=512)
    expected_batch = np.empty((512, 809), dtype=np.float32)
    prefix_semantic, prefix_numeric = hashlib.sha256(), hashlib.sha256()
    records, offsets = [], [0]
    observed_ids = set()
    for index, game in enumerate(authority.games):
        public, label, margin = read_game(game)
        if not np.all(public["global_feature_confidence"][:, 8:14] == 1):
            raise ValueError("expanded baseline tower-health globals are not fully available")
        features = augmented_features(public, layout, table)
        if len(features) != game.record["rows"]:
            raise ValueError("expanded feature length differs from audited game")
        start, end = store.offset, store.offset + len(features)
        progress[start:end] = public["global_features"][:, 0]
        current[start:end] = (public["global_features"][:, 8:11].sum(1) - public["global_features"][:, 11:14].sum(1)) / 3
        chosen = (selected >= start) & (selected < end)
        expected_batch[chosen] = features[selected[chosen] - start]
        if index < 1536:
            prefix_semantic.update(features.tobytes())
            prefix_numeric.update(np.ascontiguousarray(features[:, :425]).tobytes())
        body = public["entity_mask"].astype(bool) & (public["entity_id_confidence"] > 0)
        observed_ids.update(int(i) for i in np.unique(public["entity_ids"][body]))
        store.append(features)
        offsets.append(end)
        records.append({"path": str(game.path), "sha256": game.sha256, "cohort": game.cohort,
                        "rows": len(features), "label": label, "terminal_margin": margin,
                        "family": game.metadata["family_id"], "style": game.metadata["style"],
                        "seat": game.metadata["learner_seat"], "cluster": game.metadata["cluster_id"]})
        if index == 1535 and (end != plan.original_prefix_rows
                             or prefix_semantic.hexdigest() != plan.original_semantic_sha256
                             or prefix_numeric.hexdigest() != plan.original_numeric_sha256):
            raise ValueError("original 1536-game feature prefix changed")
        if (index + 1) % 128 == 0:
            store.release_pages()
            print(json.dumps({"audited_games": index + 1, "rows": end}), flush=True)
    if store.offset != plan.rows or len(records) != 6144:
        raise ValueError("expanded cache row or game total differs")
    cache = store.finish()
    mapped = np.memmap(output / "features.f32", mode="r", dtype="<f4", shape=(plan.rows, 809))
    if not np.array_equal(np.array(mapped[selected], copy=True), expected_batch):
        raise ValueError("expanded file-backed random batch differs")
    mapped._mmap.close()
    rows_path = output / "rows.npz"
    np.savez_compressed(rows_path, progress=progress, current_margin=current, offsets=np.asarray(offsets, dtype=np.int64))
    load_plan(plan_path)
    if any(sha(path) != expected for path, expected in authority.resources.items()):
        raise ValueError("expanded corpus authority changed during cache audit")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    result = {"status": "complete-audited-expanded-feature-cache", "games": 6144, "rows": plan.rows,
              "clusters": len({g["cluster"] for g in records}), "cache": cache,
              "rows_sha256": sha(rows_path), "plan_sha256": sha(plan_path), "implementation": sources(),
              "original_semantic_prefix_sha256": prefix_semantic.hexdigest(),
              "original_numeric_prefix_sha256": prefix_numeric.hexdigest(), "random_batch_exact": True,
              "feature_names": [*layout.names, *feature_names()], "game_records": records,
              "outcome_counts": {name: sum(g["label"] == label for g in records) for label, name in enumerate(("loss", "draw", "win"))},
              "observed_token_ids": sorted(observed_ids),
              "unresolved_observed_body_tokens": [table.vocabulary[i] for i in sorted(observed_ids)
                                                  if table.vocabulary[i].startswith(("troop_body:", "building_body:", "tower:")) and not table.resolved[i]],
              "peak_rss_bytes": peak, "outcome_fitting": False, "fitting_allowed": False, "acceptance": False,
              "scope": "Complete game audit and exact public feature extraction only. A separate model plan and full-size training memory gate remain required."}
    if result["clusters"] != 3072:
        raise ValueError("expanded cache paired-cluster count differs")
    with (output / "complete.json").open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "games": 6144, "rows": plan.rows, "peak_rss_bytes": peak}), flush=True)


if __name__ == "__main__":
    main()
