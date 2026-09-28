"""Read-only mapped features and compact scenario labels for separately gated fits."""

import json
from pathlib import Path

import numpy as np
from cache_contract import load_plan
from feature_store import file_sha
from terminal_labels import sha


def cluster_codes(cluster_names):
    """Lexicographic codes preserve the exact grouping order of string IDs."""
    names, inverse = np.unique(np.asarray(cluster_names), return_inverse=True)
    return tuple(names.tolist()), inverse.astype(np.int32)


def read_complete_cache(directory):
    directory = Path(directory)
    complete = json.loads((directory / "complete.json").read_text())
    if (complete.get("status") != "complete-audited-expanded-feature-cache"
            or complete.get("games") != 6144 or complete.get("clusters") != 3072
            or complete.get("fitting_allowed") is not False):
        raise ValueError("complete expanded cache audit required")
    plan_path = Path(__file__).resolve().parents[2] / "reports/hog26_expanded_feature_plan_20260913.json"
    plan = load_plan(plan_path)
    if (complete.get("plan_sha256") != sha(plan_path) or complete.get("implementation") != plan.implementation
            or complete.get("rows") != plan.rows or complete.get("outcome_fitting") is not False
            or complete.get("random_batch_exact") is not True
            or complete.get("original_semantic_prefix_sha256") != plan.original_semantic_sha256
            or complete.get("original_numeric_prefix_sha256") != plan.original_numeric_sha256):
        raise ValueError("expanded cache extraction authority differs")
    path = directory / "features.f32"
    if path.stat().st_size != complete["cache"]["bytes"] or file_sha(path) != complete["cache"]["sha256"]:
        raise ValueError("expanded feature cache changed")
    if file_sha(directory / "rows.npz") != complete["rows_sha256"]:
        raise ValueError("expanded row metadata changed")
    records = complete["game_records"]
    lengths = np.array([g["rows"] for g in records])
    with np.load(directory / "rows.npz", allow_pickle=False) as saved:
        progress, current, offsets = saved["progress"], saved["current_margin"], saved["offsets"]
    expected_offsets = np.r_[0, lengths.cumsum()]
    if (len(records) != 6144 or not np.array_equal(offsets, expected_offsets)
            or progress.shape != (lengths.sum(),) or current.shape != progress.shape
            or complete["cache"]["shape"] != [len(progress), 809]):
        raise ValueError("expanded cache game boundaries differ")
    cluster_names, game_clusters = cluster_codes([g["cluster"] for g in records])
    if len(cluster_names) != 3072:
        raise ValueError("expanded cluster code count differs")
    ids = np.repeat(np.arange(6144), lengths)
    labels = np.repeat([g["label"] for g in records], lengths)
    target = np.repeat([g["terminal_margin"] for g in records], lengths)
    seats = np.repeat([g["seat"] for g in records], lengths)
    styles = np.repeat([g["style"] for g in records], lengths)
    families = np.repeat([g["family"] for g in records], lengths)
    clusters = np.repeat(game_clusters, lengths)
    folds = np.array([int(f[-3:]) // 2 for f in families], dtype=np.int8)
    features = np.memmap(path, mode="r", dtype="<f4", shape=(len(progress), 809))
    evaluation = (ids, progress, labels, target, current, seats, styles, folds, clusters, families)
    return features, evaluation, complete, cluster_names
