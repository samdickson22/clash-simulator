"""Verify streaming storage against both frozen existing feature hashes."""

import hashlib
import json
import resource
import sys
from pathlib import Path

import numpy as np
import torch
from body_features import augmented_features
from body_stats import compile_body_table
from feature_store import FeatureStore
from residual_features import make_layout
from semantic_contract import load_plan, sha

PUBLIC = ("entity_ids", "entity_features", "entity_mask", "entity_id_confidence",
          "entity_feature_confidence", "hand_ids", "hand_id_confidence",
          "global_features", "global_feature_confidence")


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_streamed_feature_probe_20260913"
    if output.exists():
        raise ValueError("preserve existing streaming probe")
    source_hashes = {str(p): sha(p) for p in Path(__file__).parent.glob("*.py")}
    plan_path = root / "reports/hog26_semantic_margin_frozen_plan_20260912.json"
    plan = load_plan(plan_path)
    manifest_path = Path(plan.data.globals_directory) / "fitting_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    numeric_memory = root / "reports/hog26_residual_margin_memory_20260912.json"
    expected_numeric = json.loads(numeric_memory.read_text())["feature_matrix_sha256"]
    table = compile_body_table(plan.data.vocabulary)
    layout = make_layout(len(table.vocabulary), plan.data.hand_tokens)
    selected = np.random.default_rng(1280001).integers(0, 618149, size=512)
    expected_rows = np.empty((512, 809), dtype=np.float32)
    output.mkdir()
    cache = output / "features.f32"
    store = FeatureStore(cache, 618149, 809)
    numeric_hash = hashlib.sha256()
    for index, record in enumerate(manifest["input_games"]):
        path = Path(record["path"])
        if sha(path) != record["sha256"]:
            raise ValueError("streaming source archive changed")
        with np.load(path, allow_pickle=False) as archive:
            public = {key: archive[key] for key in PUBLIC}
        for key in ("hand_ids", "hand_id_confidence"):
            public[key] = public[key][:, :4]
        features = augmented_features(public, layout, table)
        chosen = (selected >= store.offset) & (selected < store.offset + len(features))
        expected_rows[chosen] = features[selected[chosen] - store.offset]
        numeric_hash.update(np.ascontiguousarray(features[:, :425]).tobytes())
        store.append(features)
        if (index + 1) % 128 == 0:
            store.release_pages()
            print(json.dumps({"games": index + 1, "rows": store.offset}), flush=True)
    stored = store.finish()
    if stored["sha256"] != plan.features.matrix_sha256 or numeric_hash.hexdigest() != expected_numeric:
        raise ValueError("streamed matrix differs from frozen resident feature values")
    mapped = np.memmap(cache, mode="r", dtype="<f4", shape=(618149, 809))
    actual_rows = np.array(mapped[selected], copy=True)
    if not np.array_equal(actual_rows, expected_rows):
        raise ValueError("file-backed random batch differs from original rows")
    mapped._mmap.close()
    load_plan(plan_path)
    if any(sha(path) != expected for path, expected in source_hashes.items()):
        raise ValueError("streaming probe source changed")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    result = {"status": "passed-existing-corpus-streaming-probe", "games": 1536, "cache": stored,
              "numeric_prefix_sha256": numeric_hash.hexdigest(), "random_batch_rows": 512,
              "random_batch_exact": True, "peak_rss_bytes": peak,
              "sources": source_hashes, "feature_plan_sha256": sha(plan_path),
              "manifest_sha256": sha(manifest_path), "outcome_arrays_read": False,
              "fitting": False, "acceptance": False,
              "limitations": ["This validates the existing 1536-game corpus, not a future 6144-game memory envelope.",
                              "Larger-corpus auditing and fitting still require separate complete-data and memory gates."]}
    with (output / "complete.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "peak_rss_bytes": peak}), flush=True)


if __name__ == "__main__":
    main()
