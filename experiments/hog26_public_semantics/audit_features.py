"""Stream the already audited training archives without reading outcome arrays."""

import hashlib
import json
import resource
from pathlib import Path

import numpy as np
from body_features import augmented_features, feature_names
from body_stats import compile_body_table
from residual_features import make_layout

PUBLIC_KEYS = ("entity_ids", "entity_features", "entity_mask", "entity_id_confidence",
               "entity_feature_confidence", "hand_ids", "hand_id_confidence",
               "global_features", "global_feature_confidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_public_semantic_feature_audit_20260912.json"
    if output.exists():
        raise ValueError("preserve existing feature audit")
    plan_path = root / "reports/hog26_residual_margin_frozen_plan_20260912.json"
    plan = json.loads(plan_path.read_text())
    manifest_path = root / "reports/hog26_scaling_globals_comparison_20260912/fitting_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    table = compile_body_table(plan["data"]["vocabulary"])
    sources = {str(p): sha(p) for p in sorted(Path(__file__).parent.glob("*.py"))}
    layout = make_layout(len(table.vocabulary), plan["data"]["hand_tokens"])
    digest = hashlib.sha256()
    rows = 0
    low = np.full(809, np.inf)
    high = np.full(809, -np.inf)
    for index, record in enumerate(manifest["input_games"]):
        path = Path(record["path"])
        if sha(path) != record["sha256"]:
            raise ValueError("training archive changed")
        with np.load(path, allow_pickle=False) as archive:
            public = {key: archive[key] for key in PUBLIC_KEYS}
        for key in ("hand_ids", "hand_id_confidence"):
            public[key] = public[key][:, :4]
        block = augmented_features(public, layout, table)
        rows += len(block)
        low = np.minimum(low, block.min(0))
        high = np.maximum(high, block.max(0))
        digest.update(block.tobytes())
        if (index + 1) % 128 == 0:
            print(json.dumps({"games": index + 1, "rows": rows}), flush=True)
    if len(manifest["input_games"]) != 1536 or rows != 618149:
        raise ValueError("training corpus totals changed")
    if any(sha(p) != expected for p, expected in sources.items()):
        raise ValueError("feature audit source changed during execution")
    report = {"status": "passed-public-feature-audit", "outcome_fitting": False,
              "outcome_arrays_read": False, "acceptance": False,
              "games": 1536, "rows": rows, "feature_shape": [rows, 809],
              "feature_matrix_bytes": rows * 809 * 4,
              "feature_matrix_sha256": digest.hexdigest(),
              "names": [*layout.names, *feature_names()], "min": low.tolist(), "max": high.tolist(),
              "public_body_records": table.records, "metadata_sources": table.source_hashes,
              "source_hashes": sources,
              "plan_sha256": sha(plan_path), "manifest_sha256": sha(manifest_path),
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "limitations": ["Public static descriptors are base properties, not live damage or targeting state.",
                              "Proximity is geometric distance to visible crowns, not an attack forecast.",
                              "Feature audit is not a full resident training memory audit."]}
    with output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "rows": rows}), flush=True)


if __name__ == "__main__":
    main()
