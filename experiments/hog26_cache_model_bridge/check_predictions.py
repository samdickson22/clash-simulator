"""Inference-only proof that cached public features reproduce existing model outputs."""

import json
import pickle
import resource
import sys
from pathlib import Path

import numpy as np
import torch
from feature_store import file_sha
from residual_features import make_layout
from scalar_features import build_game_features, feature_names
from scalar_models import GlobalWDL, _available
from semantic_contract import load_plan, sha

PUBLIC = ("entity_ids", "entity_features", "entity_mask", "entity_id_confidence",
          "entity_feature_confidence", "hand_ids", "hand_id_confidence",
          "global_features", "global_feature_confidence")


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_cached_model_inference_bridge_20260913.json"
    if output.exists():
        raise ValueError("preserve existing cache inference bridge")
    feature_plan_path = root / "reports/hog26_semantic_margin_frozen_plan_20260912.json"
    feature_plan = load_plan(feature_plan_path)
    probe_path = root / "reports/hog26_streamed_feature_probe_20260913/complete.json"
    probe = json.loads(probe_path.read_text())
    cache_path = probe_path.parent / "features.f32"
    if (probe["status"] != "passed-existing-corpus-streaming-probe" or not probe["random_batch_exact"]
            or file_sha(cache_path) != feature_plan.features.matrix_sha256):
        raise ValueError("exact existing-corpus feature cache required")
    resources = {str(feature_plan_path): sha(feature_plan_path), str(probe_path): sha(probe_path),
                 str(cache_path): probe["cache"]["sha256"], str(Path(__file__)): sha(__file__)}
    layout = make_layout(len(feature_plan.data.vocabulary), feature_plan.data.hand_tokens)
    full_names = feature_names(len(feature_plan.data.vocabulary))
    global_columns = [layout.names.index(f"global{i}") for i in range(18)] + [layout.names.index(f"global{i}.confidence") for i in range(18)]
    mapped = np.memmap(cache_path, mode="r", dtype="<f4", shape=(618149, 809))
    globals_ = np.empty((618149, 36), dtype=np.float32)
    current = np.empty(618149, dtype=np.float32)
    offsets = [0]
    manifest_path = Path(feature_plan.data.globals_directory) / "fitting_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    resources[str(manifest_path)] = sha(manifest_path)
    for record in manifest["input_games"]:
        if sha(record["path"]) != record["sha256"]:
            raise ValueError("inference bridge source game changed")
        with np.load(record["path"], allow_pickle=False) as archive:
            public = {key: archive[key] for key in PUBLIC}
        for key in ("hand_ids", "hand_id_confidence"):
            public[key] = public[key][:, :4]
        start, end = offsets[-1], offsets[-1] + len(public["global_features"])
        compact = np.array(mapped[start:end, :425], copy=True)
        restored = np.zeros((end - start, len(full_names)), dtype=np.float32)
        restored[:, layout.columns] = compact * np.asarray(layout.scales, dtype=np.float32)
        original = build_game_features(**public, vocabulary_size=len(feature_plan.data.vocabulary))
        if not np.array_equal(restored, original):
            raise ValueError("compact cache does not restore exact original tree features")
        g, confidence = torch.from_numpy(public["global_features"]), torch.from_numpy(public["global_feature_confidence"])
        expected_global = torch.cat((_available(g, confidence), confidence), -1).numpy()
        inputs = np.ascontiguousarray(compact[:, global_columns])
        if not np.array_equal(inputs, expected_global):
            raise ValueError("cached globals differ from original neural inputs")
        globals_[start:end] = inputs
        current[start:end] = (public["global_features"][:, 8:11].sum(1) - public["global_features"][:, 11:14].sum(1)) / 3
        offsets.append(end)
    if offsets[-1] != 618149 or len(offsets) != 1537:
        raise ValueError("inference bridge corpus boundaries differ")
    neural = []
    for seed in (1279501, 1279502):
        for fold in range(4):
            stem = f"seed{seed}-fold{fold}"
            checkpoint = Path(feature_plan.data.globals_directory) / (stem + ".pt")
            predictions = Path(feature_plan.data.globals_directory) / (stem + "-predictions.npz")
            resources[str(checkpoint)], resources[str(predictions)] = sha(checkpoint), sha(predictions)
            model = GlobalWDL()
            model.load_state_dict(torch.load(checkpoint, weights_only=True, map_location="cpu"))
            model.eval()
            with np.load(predictions, allow_pickle=False) as saved:
                expected = saved["probabilities"]
            with torch.inference_mode():
                for start, end in zip(offsets[:-1], offsets[1:], strict=True):
                    actual = model.network(torch.from_numpy(globals_[start:end])).softmax(-1).numpy()
                    if not np.array_equal(actual, expected[start:end]):
                        raise ValueError("cached neural inputs do not reproduce saved probabilities")
            neural.append({"seed": seed, "fold": fold, "exact": True})
            print(json.dumps({"model": "globals", **neural[-1]}), flush=True)
    sys.path.insert(0, "/Users/sam/.cache/clasher-margin-tree-diagnostic")
    import sklearn

    if sklearn.__version__ != "1.7.2":
        raise ValueError("tree runtime differs from the original comparison")
    trees = []
    for fold in range(4):
        stem = f"seed1279501-fold{fold}"
        directory = root / "reports/hog26_scaling_tree_comparison_20260912"
        checkpoint, predictions = directory / (stem + ".pkl"), directory / (stem + "-predictions.npz")
        resources[str(checkpoint)], resources[str(predictions)] = sha(checkpoint), sha(predictions)
        with checkpoint.open("rb") as stream:
            model = pickle.load(stream)
        with np.load(predictions, allow_pickle=False) as saved:
            expected = saved["margin"]
        for start in range(0, len(current), 2048):
            end = min(start + 2048, len(current))
            restored = np.zeros((end - start, len(full_names)), dtype=np.float32)
            restored[:, layout.columns] = np.array(mapped[start:end, :425], copy=True) * np.asarray(layout.scales, dtype=np.float32)
            actual = np.clip(current[start:end] + model.predict(restored), -1, 1)
            if not np.array_equal(actual, expected[start:end]):
                raise ValueError("reconstructed cached tree inputs do not reproduce saved margins")
        trees.append({"fold": fold, "exact": True})
        print(json.dumps({"model": "tree", **trees[-1]}), flush=True)
    mapped._mmap.close()
    load_plan(feature_plan_path)
    for path, expected in resources.items():
        if file_sha(path) != expected:
            raise ValueError("cache inference bridge resource changed")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    with output.open("x") as stream:
        json.dump({"status": "exact-cached-model-inference-bridge", "games": 1536, "rows": 618149,
                   "global_models": neural, "tree_models": trees, "all_original_tree_features_restored_exactly": True,
                   "all_original_global_inputs_exact": True, "resources": resources, "peak_rss_bytes": peak,
                   "outcome_arrays_read": False, "fitting": False, "acceptance": False,
                   "limitations": ["This proves cached-input inference equivalence, not compact-tree retraining equivalence.",
                                   "Larger-corpus training still requires its own complete-data and memory gates."]}, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
